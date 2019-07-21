// Copyright (C) 2018-2019  Nexedi SA and Contributors.
//                          Kirill Smelkov <kirr@nexedi.com>
//
// This program is free software: you can Use, Study, Modify and Redistribute
// it under the terms of the GNU General Public License version 3, or (at your
// option) any later version, as published by the Free Software Foundation.
//
// You can also Link and Combine this program with other software covered by
// the terms of any of the Free Software licenses or any of the Open Source
// Initiative approved licenses and Convey the resulting work. Corresponding
// source of such a combination shall include the source code for all other
// software used.
//
// This program is distributed WITHOUT ANY WARRANTY; without even the implied
// warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
//
// See COPYING file for full licensing terms.
// See https://www.nexedi.com/licensing for rationale and options.

// pygolang C part: provides runtime implementation such as panic and channels.
//
// C++ (not C) is used:
// - to implement C-level panic (via C++ exceptions).
// - to provide chan<T> template that can be used as chan[T] in Cython.
// - because Cython (currently ?) does not allow to add methods to `cdef struct`.

#include "golang.h"

#include <exception>
#include <string>
#include <string.h>

// for semaphores (need pythread.h but it depends on PyAPI_FUNC from outside)
#include <Python.h>
#include <pythread.h>

// XXX -> better use c.h or ccan/array_size.h ?
#ifndef ARRAY_SIZE
# define ARRAY_SIZE(A) (sizeof(A) / sizeof((A)[0]))
#endif
#include "../3rdparty/include/linux/list.h"

using std::string;
using std::exception;


// ---- panic ----

// panic throws exception that represents C-level panic.
// the exception can be caught at C++ level via try/catch and recovered via recover.
struct PanicError : exception {
	const char *arg;
};

void panic(const char *arg) {
	PanicError _; _.arg = arg;
	throw _;
}

// recover recovers from exception thrown by panic.
// it returns: !NULL - there was panic with that argument. NULl - there was no panic.
// if another exception was thrown - recover rethrows it.
const char *recover() {
	// if PanicError was thrown - recover from it
	try {
		throw;
	} catch (PanicError &exc) {
		return exc.arg;
	}

	return NULL;
}


// bug indicates internl bug in golang implementation.
struct Bug : exception {
	const string msg;

	virtual const char *what() const throw() {
		return msg.c_str();
	}

	Bug(const string &msg) : msg("BUG: " + msg) {}
};

void bug(const char *msg) {
	throw Bug(msg);
}


// ---- semaphores ----

// init -> PyThread_init_thread (so that there is no concurrent calls to
// PyThread_init_thread from e.g. PyThread_allocate_lock)
//
// XXX -> explicit call from golang -> and detect gevent'ed envirtnment from there.
static struct _init_pythread {
    _init_pythread() {
        PyThread_init_thread();
    }
} _init_pythread;

// Sema provides semaphore.
//
// Reuse Python semaphore implementation for portability. In Python semaphores
// do not depend on GIL and by reusing the implementation we can offload us
// from covering different systems.
//
// On POSIX, for example, Python uses sem_init(process-private) + sem_post/sem_wait.
//
// XXX recheck gevent case
struct Sema {
    // python calls it "lock", but it is actually a semaphore.
    // and in particular can be released by thread different from thread that acquired it.
    PyThread_type_lock _pysema;

    Sema();
    ~Sema();
    void acquire();
    void release();

private:
    Sema(const Sema&); // dont copy
};

Sema::Sema() {
    Sema *sema = this;

    sema->_pysema = PyThread_allocate_lock();
    if (!sema->_pysema)
        panic("sema: alloc failed");
}

Sema::~Sema() {
    Sema *sema = this;

    PyThread_free_lock(sema->_pysema);
    sema->_pysema = NULL;
}

void Sema::acquire() {
    Sema *sema = this;
    PyThread_acquire_lock(sema->_pysema, WAIT_LOCK);
}

void Sema::release() {
    Sema *sema = this;
    PyThread_release_lock(sema->_pysema);
}


// ---- channels -----

// _chan is a raw channel with Go semantic.
//
// Over raw channel the data is sent/received via elemsize'ed memcpy of void*
// and the caller must make sure to pass correct arguments.
//
// See chan<T> for type-safe wrapper.
//
// _chan is not related to Python runtime and works without GIL.
struct _chan {
    unsigned    _cap;       // channel capacity (in elements)
    unsigned    _elemsize;  // size of element

    Sema        _mu;        // XXX need to be only Mutex
    // ._dataq       deque *: data buffer                    XXX -> [_cap*_elemsize]
    list_head   _recvq;     // blocked receivers (_ -> _RecvSendWaiting.in_rxtxq)
    list_head   _sendq;     // blocked senders   (_ -> _RecvSendWaiting.in_rxtxq)
    bool        _closed;


    void send(void *ptx);
    bool recv_(void *prx);
    void recv(void *prx);
    bool _trysend(void *tx);
    bool _tryrecv(void *prx, bool *pok);
    void close();
    unsigned len();
};

struct _WaitGroup;

// _RecvSendWaiting represents a receiver/sender waiting on a chan.
struct _RecvSendWaiting {
    _WaitGroup  *group; // group of waiters this receiver/sender is part of
    _chan       *chan;  // channel receiver/sender is waiting on

    // XXX + op

    list_head   in_rxtxq; // in recv or send queue of a channel (_chan._recvq|_sendq -> _)
    list_head   in_group; // in wait group (_WaitGroup.waitq -> _)

    // recv: on wakeup: sender|closer -> receiver
    // send: ptr-to data to send
    void    *pdata;
    // on wakeup: whether recv/send succeeded  (send fails on close)
    bool    ok;

    _RecvSendWaiting(_WaitGroup *group, _chan *ch);
};

// _WaitGroup is a group of waiting senders and receivers.
//
// Only 1 waiter from the group can succeed waiting.
struct _WaitGroup {
    list_head  waitq;   // waiters of this group (_ -> _RecvSendWaiting.in_group)
    Sema       _sema;   // used for wakeup (must be semaphore)

    Sema       _mu;     // lock    NOTE ∀ chan order is always: chan._mu > ._mu
    // on wakeup: sender|receiver -> group:
    //   .which  _{Send|Recv}Waiting     instance which succeeded waiting.
    _RecvSendWaiting    *which;


    _WaitGroup();
    bool try_to_win(_RecvSendWaiting *waiter);
    void wait();
    void wakeup();
};


// XXX place=?
_RecvSendWaiting::_RecvSendWaiting(_WaitGroup *group, _chan *ch) {
    _RecvSendWaiting *w = this;
    w->group = group;
    w->chan  = ch;
    INIT_LIST_HEAD(&w->in_rxtxq);
    INIT_LIST_HEAD(&w->in_group);
    list_add_tail(&w->in_group, &group->waitq);
}

_WaitGroup::_WaitGroup() {
    _WaitGroup *group = this;
    INIT_LIST_HEAD(&group->waitq);
    group->_sema.acquire();
    group->which = NULL;
}

// try_to_win tries to win waiter after it was dequeued from a channel's {_send|_recv}q.
//
// -> won: true if won, false - if not.
bool _WaitGroup::try_to_win(_RecvSendWaiting *waiter) { // -> won
    _WaitGroup *group = this;

    bool won;
    group->_mu.acquire();
        if (group->which != NULL) {
            won = false;
        }
        else {
            group->which = waiter;
            won = true;
        }
    group->_mu.release();
    return won;
}

// wait waits for winning case of group to complete.
void _WaitGroup::wait() {
    _WaitGroup *group = this;
    group->_sema.acquire();
}

// wakeup wakes up the group.
//
// prior to wakeup try_to_win must have been called.
// in practice this means that waiters queued to chan.{_send|_recv}q must
// be dequeued with _dequeWaiter.
void _WaitGroup::wakeup() {
    _WaitGroup *group = this;
    if (group->which == NULL)
        bug("wakeup: group.which=nil");
    group->_sema.release();
}

// _dequeWaiter dequeues a send or recv waiter from a channel's _recvq or _sendq.
//
// the channel owning {_recv|_send}q must be locked.
_RecvSendWaiting *_dequeWaiter(list_head *queue) {
    while (!list_empty(queue)) {
        _RecvSendWaiting *w = list_entry(queue->next, _RecvSendWaiting, in_rxtxq);
        list_del_init(&w->in_rxtxq);
        // if this waiter can win its group - return it.
        // if not - someone else from its group already has won, and so we anyway have
        // to remove the waiter from the queue.
        if (w->group->try_to_win(w)) {
            return w;
        }
    }

    return NULL;
}

// _makechan creates new _chan(elemsize, size).
_chan *_makechan(unsigned elemsize, unsigned size) {
    _chan *ch;
    ch = (_chan *)malloc(sizeof(_chan) + size*elemsize);
    if (ch == NULL)
        return NULL;
    memset((void *)ch, 0, sizeof(*ch));
    new (&ch->_mu) Sema();

    ch->_cap      = size;
    ch->_elemsize = elemsize;
    ch->_closed   = false;

    INIT_LIST_HEAD(&ch->_recvq);
    INIT_LIST_HEAD(&ch->_sendq);

    return ch;
}


void _blockforever();


// send sends data to a receiver.
//
// sizeof(*ptx) must be ch._elemsize.
void _chansend(_chan *ch, void *ptx) { ch->send(ptx); }
void _chan::send(void *ptx) {
    _chan *ch = this;

    if (ch == NULL)
        _blockforever();

    ch->_mu.acquire();
        bool ok = ch->_trysend(ptx);
        if (ok)
            return;

        _WaitGroup         g;
        _RecvSendWaiting   me(&g, ch);
        me.pdata    = ptx;
        me.ok       = false;

        list_add_tail(&me.in_rxtxq, &ch->_sendq);
    ch->_mu.release();

    printf("send: -> g.wait()...\n");
    g.wait();
    printf("send: -> woken up\n");
    if (g.which != &me)
        bug("chansend: g.which != me");
    if (!me.ok)
        panic("send on closed channel");
}

// recv_ is "comma-ok" version of recv.
//
// ok is true - if receive was delivered by a successful send.
// ok is false - if receive is due to channel being closed and empty.
//
// sizeof(*prx) must be ch._elemsize | prx=NULL.
bool _chanrecv_(_chan *ch, void *prx) { return ch->recv_(prx); }
bool _chan::recv_(void *prx) { // -> ok
    _chan *ch = this;

    if (ch == NULL)
        _blockforever();

    ch->_mu.acquire();
        bool ok, ready = ch->_tryrecv(prx, &ok);
        if (ready)
            return ok;

        _WaitGroup         g;
        _RecvSendWaiting   me(&g, ch);
        me.pdata    = prx;
        me.ok       = false;

        list_add_tail(&me.in_rxtxq, &ch->_recvq);
    ch->_mu.release();

    printf("recv: -> g.wait()...\n");
    g.wait();
    if (g.which != &me)
        bug("chanrecv: g.which != me");
    printf("recv: -> woken up;  ok=%i\n", me.ok);
    return me.ok;
}

// recv receives from the channel.
//
// received value is put into *prx.
void _chanrecv(_chan *ch, void *prx) { ch->recv(prx); }
void _chan::recv(void *prx) {
    _chan *ch = this;
    (void)ch->recv_(prx);
    return;
}


// _trysend(ch, obj) -> ok
//
// must be called with ._mu held.
// if ok or panic - returns with ._mu released.
// if !ok - returns with ._mu still being held.
bool _chan::_trysend(void *ptx) { // -> ok
    _chan *ch = this;

    if (ch->_closed) {
        ch->_mu.release();
        panic("send on closed channel");
    }

    // synchronous channel
    if (ch->_cap == 0) {
        _RecvSendWaiting *recv = _dequeWaiter(&ch->_recvq);
        if (recv == NULL)
            return false;

        ch->_mu.release();
        // XXX vvv was recv->wakeup(ptx, true);
        memcpy(recv->pdata, ptx, ch->_elemsize);
        recv->ok = true;
        recv->group->wakeup();
        return true;
    }
    return false;    // XXX stub
#if 0
    // buffered channel
    else:
        if len(ch._dataq) >= ch._cap:
            return false

        ch._dataq.append(obj)
        recv = _dequeWaiter(ch._recvq)
        ch._mu.release()
        if recv is not None:
            rx = ch._dataq.popleft()
            recv.wakeup(rx, true)
        return true
#endif
}


// _tryrecv() -> rx_=(rx, ok), ready
//
// must be called with ._mu held.
// if ready or panic - returns with ._mu released.
// if !ready - returns with ._mu still being held.
//
// if !ready - (*prx, *pok) are left unmodified.
bool _chan::_tryrecv(void *prx, bool *pok) { // -> ready
    _chan *ch = this;

    // buffered
#if 0
    if len(ch._dataq) > 0:
        rx = ch._dataq.popleft()

        # wakeup a blocked writer, if there is any
        send = _dequeWaiter(ch._sendq)
        ch._mu.release()
        if send is not None:
            ch._dataq.append(send.obj)
            send.wakeup(true)

        return (rx, true), true
#endif

    // closed
    if (ch->_closed) {
        ch->_mu.release();
        memset(prx, 0, ch->_elemsize);
        *pok = false;
        return true;
    }

    // sync | empty: there is waiting writer
    _RecvSendWaiting *send = _dequeWaiter(&ch->_sendq);
    if (send == NULL)
        return false;

    ch->_mu.release();
    memcpy(prx, send->pdata, ch->_elemsize);
    *pok = true;
    // XXX vvv was send.wakeup(true)
    send->ok = true;
    send->group->wakeup();
    return true;
}

// close closes sending side of the channel.
void _chanclose(_chan *ch) { ch->close(); }
void _chan::close() {
    _chan *ch = this;

    if (ch == NULL)
        panic("close of nil channel");

    // XXX stub
    if (ch->_closed)
        panic("close of closed channel");
    ch->_closed = true;

#if 0
    recvv = []
    sendv = []

    with ch._mu:
        if ch._closed:
            panic("close of closed channel")
        ch._closed = true

        # schedule: wake-up all readers
        while 1:
            recv = _dequeWaiter(ch._recvq)
            if recv is None:
                break
            recvv.append(recv)

        # schedule: wake-up all writers (they will panic)
        while 1:
            send = _dequeWaiter(ch._sendq)
            if send is None:
                break
            sendv.append(send)

    # perform scheduled wakeups outside of ._mu
    for recv in recvv:
        recv.wakeup(None, false)
    for send in sendv:
        send.wakeup(false)
#endif
}

// len returns current number of buffered elements.
unsigned _chanlen(_chan *ch) { return ch->len(); }
unsigned _chan::len() {
    //_chan *ch = this;
    panic("_chan::len: TODO");
}


// _blockforever blocks current goroutine forever.
void _blockforever() {
    panic("_blockforever: TODO");
#if 0
    // take a lock twice. It will forever block on the second lock attempt.
    // Under gevent, similarly to Go, this raises "LoopExit: This operation
    // would block forever", if there are no other greenlets scheduled to be run.
    dead = threading.Lock()
    dead.acquire()
    dead.acquire()
#endif
}
