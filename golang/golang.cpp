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

// Pygolang C part: provides runtime implementation of panic, channels, etc.
//
// C++ (not C) is used:
// - to implement C-level panic (via C++ exceptions).
// - to provide chan<T> template that can be used as chan[T] in Cython.
// - because Cython (currently ?) does not allow to add methods to `cdef struct`.

#include "golang.h"

#include <exception>
#include <string>
#include <algorithm>
#include <random>
#include <mutex>    // lock_guard

#include <string.h>

// for semaphores (need pythread.h but it depends on PyAPI_FUNC from Python.h)
#include <Python.h>
#include <pythread.h>

// XXX -> better use c.h or ccan/array_size.h ?
// XXX move list.h into here?
#ifndef ARRAY_SIZE
# define ARRAY_SIZE(A) (sizeof(A) / sizeof((A)[0]))
#endif
#include "../3rdparty/include/linux/list.h"

using std::string;
using std::vector;
using std::exception;

namespace golang {

// ---- panic ----

struct PanicError : exception {
	const char *arg;
};

// panic throws exception that represents C-level panic.
// the exception can be caught at C++ level via try/catch and recovered via recover.
void panic(const char *arg) {
	PanicError _; _.arg = arg;
	throw _;
}

// recover recovers from exception thrown by panic.
// it returns: !NULL - there was panic with that argument. NULL - there was no panic.
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


// bug indicates internal bug in golang implementation.
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
// XXX -> explicit call from golang -> and detect gevent'ed environment from there.
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
    Sema(const Sema&);      // don't copy
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

// Mutex provides mutex.
// currently implemented via Sema.
struct Mutex {
    void lock()     { _sema.acquire();  }
    void unlock()   { _sema.release();  }
    Mutex() {}

private:
    Sema _sema;
    Mutex(const Mutex&);    // don't copy
};

// with_lock imitates with mu   XXX
typedef std::lock_guard<Mutex> with_lock;

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

    Mutex       _mu;
    list_head   _recvq;     // blocked receivers (_ -> _RecvSendWaiting.in_rxtxq)
    list_head   _sendq;     // blocked senders   (_ -> _RecvSendWaiting.in_rxtxq)
    bool        _closed;

    // data queue (circular buffer) goes past _chan memory and occupies [_cap*_elemsize] bytes.
    unsigned    _dataq_n;   // total number of entries in dataq
    unsigned    _dataq_r;   // index for next read  (in elements; can be used only if _dataq_n > 0)
    unsigned    _dataq_w;   // index for next write (in elements; can be used only if _dataq_n < _cap)

    void send(const void *ptx);
    bool recv_(void *prx);
    void recv(void *prx);
    bool _trysend(const void *tx);
    bool _tryrecv(void *prx, bool *pok);
    void close();
    unsigned len();

    void _dataq_append(const void *ptx);
    void _dataq_popleft(void *prx);
private:
    _chan(const _chan&);    // don't copy
};

struct _WaitGroup;

// _RecvSendWaiting represents a receiver/sender waiting on a chan.
struct _RecvSendWaiting {
    _WaitGroup  *group; // group of waiters this receiver/sender is part of
    _chan       *chan;  // channel receiver/sender is waiting on

    list_head   in_rxtxq; // in recv or send queue of a channel (_chan._recvq|_sendq -> _)
//  list_head   in_group; // in wait group (_WaitGroup.waitq -> _)

    // recv: on wakeup: sender|closer -> receiver
    // send: ptr-to data to send
    void    *pdata;
    // on wakeup: whether recv/send succeeded  (send fails on close)
    bool    ok;

    // this case is used in its select as case #sel_n
    int     sel_n;

    _RecvSendWaiting();
    void init(_WaitGroup *group, _chan *ch);
private:
    _RecvSendWaiting(const _RecvSendWaiting&);  // don't copy
};

// _WaitGroup is a group of waiting senders and receivers.
//
// Only 1 waiter from the group can succeed waiting.
struct _WaitGroup {
//  list_head  waitq;   // waiters of this group (_ -> _RecvSendWaiting.in_group)
    Sema       _sema;   // used for wakeup (must be semaphore)

    Mutex      _mu;     // lock    NOTE ∀ chan order is always: chan._mu > ._mu
    // on wakeup: sender|receiver -> group:
    //   .which  _{Send|Recv}Waiting     instance which succeeded waiting.
    _RecvSendWaiting    *which;


    _WaitGroup();
    bool try_to_win(_RecvSendWaiting *waiter);
    void wait();
    void wakeup();
private:
    _WaitGroup(const _WaitGroup&);  // don't copy
};


// Default _RecvSendWaiting ctor creates zero-value _RecvSendWaiting.
// zero value _RecvSendWaiting is invalid and must be initialized via .init before use.
// XXX place=?
_RecvSendWaiting::_RecvSendWaiting() {
    _RecvSendWaiting *w = this;
    bzero((void *)w, sizeof(*w));
}

// init initializes waiter to be part of group waiting on ch.
void _RecvSendWaiting::init(_WaitGroup *group, _chan *ch) {
    _RecvSendWaiting *w = this;
    if (w->group != NULL)
        bug("_RecvSendWaiting: double init");
    w->group = group;
    w->chan  = ch;
    INIT_LIST_HEAD(&w->in_rxtxq);
//  INIT_LIST_HEAD(&w->in_group);
    w->pdata = NULL;
    w->ok    = false;
    w->sel_n = -1;
//  list_add_tail(&w->in_group, &group->waitq);
}

_WaitGroup::_WaitGroup() {
    _WaitGroup *group = this;
//  INIT_LIST_HEAD(&group->waitq);
    group->_sema.acquire();
    group->which = NULL;
}

// try_to_win tries to win waiter after it was dequeued from a channel's {_send|_recv}q.
//
// -> won: true if won, false - if not.
bool _WaitGroup::try_to_win(_RecvSendWaiting *waiter) { // -> won
    _WaitGroup *group = this;

    bool won;
    group->_mu.lock();
        if (group->which != NULL) {
            won = false;
        }
        else {
            group->which = waiter;
            won = true;
        }
    group->_mu.unlock();
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
void _chansend(_chan *ch, const void *ptx) { ch->send(ptx); }
void _chan::send(const void *ptx) {
    _chan *ch = this;

    if (ch == NULL)
        _blockforever();

    ch->_mu.lock();
        bool done = ch->_trysend(ptx);
        if (done)
            return;

        _WaitGroup         g;
        _RecvSendWaiting   me; me.init(&g, ch);
        me.pdata    = (void *)ptx; // we add it to _sendq; the memory will be only read
        me.ok       = false;

        list_add_tail(&me.in_rxtxq, &ch->_sendq);
    ch->_mu.unlock();

    //printf("send: -> g.wait()...\n");
    g.wait();
    //printf("send: -> woken up\n");
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
// sizeof(*prx) must be ch._elemsize | prx=NULL.    XXX do we need prx=NULL ?
bool _chanrecv_(_chan *ch, void *prx) { return ch->recv_(prx); }
bool _chan::recv_(void *prx) { // -> ok
    _chan *ch = this;

    if (ch == NULL)
        _blockforever();

    ch->_mu.lock();
        bool ok, done = ch->_tryrecv(prx, &ok);
        if (done) {
            //printf("recv: -> tryrecv done; ok=%i\n", ok);
            return ok;
        }

        _WaitGroup         g;
        _RecvSendWaiting   me; me.init(&g, ch);
        me.pdata    = prx;
        me.ok       = false;

        list_add_tail(&me.in_rxtxq, &ch->_recvq);
    ch->_mu.unlock();

    //printf("recv: -> g.wait()...\n");
    g.wait();
    if (g.which != &me)
        bug("chanrecv: g.which != me");
    //printf("recv: -> woken up;  ok=%i\n", me.ok);
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


// _trysend(ch, obj) -> done
//
// must be called with ._mu held.
// if done or panic - returns with ._mu released.
// if !done - returns with ._mu still being held.
bool _chan::_trysend(const void *ptx) { // -> done
    _chan *ch = this;

    if (ch->_closed) {
        ch->_mu.unlock();
        panic("send on closed channel");
    }

    // synchronous channel
    if (ch->_cap == 0) {
        _RecvSendWaiting *recv = _dequeWaiter(&ch->_recvq);
        if (recv == NULL)
            return false;

        ch->_mu.unlock();
        // XXX vvv was recv->wakeup(ptx, true);
        memcpy(recv->pdata, ptx, ch->_elemsize);
        recv->ok = true;
        recv->group->wakeup();
        return true;
    }
    // buffered channel
    else {
        if (ch->_dataq_n >= ch->_cap)
            return false;

        ch->_dataq_append(ptx);
        _RecvSendWaiting *recv = _dequeWaiter(&ch->_recvq);
        if (recv != NULL) {
            ch->_dataq_popleft(recv->pdata);
            ch->_mu.unlock();
            // XXX was recv.wakeup(rx, true)
            recv->ok = true;
            recv->group->wakeup();
        } else {
            ch->_mu.unlock();
        }
        return true;
    }
}


// _tryrecv() -> rx_=(rx, ok), done
//
// must be called with ._mu held.
// if done or panic - returns with ._mu released.
// if !done - returns with ._mu still being held.
//
// if !done - (*prx, *pok) are left unmodified.
bool _chan::_tryrecv(void *prx, bool *pok) { // -> done
    _chan *ch = this;

    // buffered
    if (ch->_dataq_n > 0) {
        ch->_dataq_popleft(prx);
        *pok = true;

        // wakeup a blocked writer, if there is any
        _RecvSendWaiting *send = _dequeWaiter(&ch->_sendq);
        if (send != NULL) {
            ch->_dataq_append(send->pdata);
            ch->_mu.unlock();
            // XXX was send.wakeup(true)
            send->ok = true;
            send->group->wakeup();
        } else {
            ch->_mu.unlock();
        }

        return true;
    }

    // closed
    if (ch->_closed) {
        ch->_mu.unlock();
        memset(prx, 0, ch->_elemsize);
        *pok = false;
        return true;
    }

    // sync | empty: there is waiting writer
    _RecvSendWaiting *send = _dequeWaiter(&ch->_sendq);
    if (send == NULL)
        return false;

    ch->_mu.unlock();
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

    ch->_mu.lock();
        if (ch->_closed) {
            ch->_mu.unlock();
            panic("close of closed channel");
        }
        ch->_closed = true;

        // wake-up all readers
        while (1) {
            _RecvSendWaiting *recv = _dequeWaiter(&ch->_recvq);
            if (recv == NULL)
                break;

            ch->_mu.unlock();
            // XXX was recv.wakeup(None, false)
            memset(recv->pdata, 0, ch->_elemsize);
            recv->ok = false;
            recv->group->wakeup();
            ch->_mu.lock();
        }

        // wake-up all writers (they will panic)
        while (1) {
            _RecvSendWaiting *send = _dequeWaiter(&ch->_sendq);
            if (send == NULL)
                break;

            ch->_mu.unlock();
            // XXX was send.wakeup(false)
            send->ok = false;
            send->group->wakeup();
            ch->_mu.lock();
        }
    ch->_mu.unlock();
}

// len returns current number of buffered elements.
unsigned _chanlen(_chan *ch) { return ch->len(); }
unsigned _chan::len() {
    _chan *ch = this;
    if (ch == NULL)
        return 0; // len(nil) = 0

    ch->_mu.lock(); // only to make valgrind happy
    unsigned len = ch->_dataq_n;
    ch->_mu.unlock();
    return len;
}

// _dataq_append appends next element to ch._dataq.
// called with ch._mu locked.
void _chan::_dataq_append(const void *ptx) {
    _chan *ch = this;

    if (ch->_dataq_n >= ch->_cap)
        bug("chan: dataq.append on full dataq");
    if (ch->_dataq_w >= ch->_cap)
        bug("chan: dataq.append: w >= cap");

    memcpy(&((char *)(ch+1))[ch->_dataq_w * ch->_elemsize], ptx, ch->_elemsize);
    ch->_dataq_w++; ch->_dataq_w %= ch->_cap;
    ch->_dataq_n++;
}

// _dataq_popleft pops oldest element from ch._dataq into *prx.
// called with ch._mu locked.
void _chan::_dataq_popleft(void *prx) {
    _chan *ch = this;

    if (ch->_dataq_n == 0)
        bug("chan: dataq.popleft on empty dataq");
    if (ch->_dataq_r >= ch->_cap)
        bug("chan: dataq.popleft: r >= cap");

    memcpy(prx, &((char *)(ch+1))[ch->_dataq_r * ch->_elemsize], ch->_elemsize);
    ch->_dataq_r++; ch->_dataq_r %= ch->_cap;
    ch->_dataq_n--;
}


// ---- select ----

// _default represents default case for _select.
const _selcase _default = {
    .ch     = NULL,
    .op     = _DEFAULT,
    .data   = NULL,
    .rxok   = NULL,
};

// _chanselect executes one ready send or receive channel case.
//
// if no case is ready and default case was provided, select chooses default.
// if no case is ready and default was not provided, select blocks until one case becomes ready.
//
// returns: selected case number and receive info (None if send case was selected).
//
// example:
//
//   _, _rx = select(
//       ch1.recv,           # 0
//       ch2.recv_,          # 1
//       (ch2.send, obj2),   # 2
//       default,            # 3
//   )
//   if _ == 0:
//       # _rx is what was received from ch1
//       ...
//   if _ == 1:
//       # _rx is (rx, ok) of what was received from ch2
//       ...
//   if _ == 2:
//       # we know obj2 was sent to ch2
//       ...
//   if _ == 3:
//       # default case
//       ...
//
// XXX update ^^^
// XXX casev is not modified and can be used for next _chanselect calls.
int _chanselect(const _selcase *casev, int casec) {
    if (casec < 0)
        panic("select: casec < 0");

    // select promise: if multiple cases are ready - one will be selected randomly
    vector<int> nv(casec); // n -> n(case)      TODO stack-allocate for small casec
    for (int i=0; i <casec; i++)
        nv[i] = i;
    std::random_shuffle(nv.begin(), nv.end());

    // first pass: poll all cases and bail out in the end if default was provided
    int  ndefault = -1;
    bool havenonnil = false; // whether we have at least one !nil channel
    for (auto n : nv) {
        const _selcase *cas = &casev[n];
        _chan *ch = cas->ch;

        // default: remember we have it
        if (cas->op == _DEFAULT) {
            if (ndefault != -1)
                panic("select: multiple default");
            ndefault = n;
        }

        // send
        else if (cas->op == _CHANSEND) {
            if (ch != NULL) {   // nil chan is never ready
                ch->_mu.lock();
                if (1) {
                    bool done = ch->_trysend(cas->data);
                    if (done)
                        return n;
                }
                ch->_mu.unlock();
                havenonnil = true;
            }
        }

        // recv
        else if (cas->op == _CHANRECV || cas->op == _CHANRECV_) {
            bool commaok = (cas->op == _CHANRECV_);

            if (ch != NULL) {   // nil chan is never ready
                ch->_mu.lock();
                if (1) {
                    bool ok, done = ch->_tryrecv(cas->data, &ok);
                    if (done) {
                        if (commaok)
                            *cas->rxok = ok;
                        return n;
                    }
                }
                ch->_mu.unlock();
                havenonnil = true;
            }
        }

        // bad case
        else {
            panic("select: invalid op");
        }
    }

    // execute default if we have it
    if (ndefault != -1)
        return ndefault;

    // select{} or with nil-channels only -> block forever
    if (!havenonnil)
        _blockforever();

    // second pass: subscribe and wait on all rx/tx cases
    _WaitGroup  g;
    vector<_RecvSendWaiting>  waitv; // storage for waiters we create
    waitv.reserve(casec);            // the memory must _not_ move
    // XXX defer deque all from waitv

    int selected = -1;
    for (auto n : nv) {
        const _selcase *cas = &casev[n];
        _chan *ch = cas->ch;

        if (ch == NULL) // nil chan is never ready
            continue;

        ch->_mu.lock();
        with_lock _(g._mu); // with, because _trysend may panic
            // a case that we previously queued already won while we were
            // queing other cases.
            if (g.which != NULL) {
                ch->_mu.unlock();
                break;
            }

            // send
            if (cas->op == _CHANSEND) {
                bool done = ch->_trysend(cas->data);
                if (done) {
                    // don't let already queued cases win
                    g.which = "tx prepoll won"; // !NULL    XXX -> current waiter?
                    selected = n;
                    break;
                }

                int l = waitv.size();
                if (l >= casec)
                    bug("select: waitv overflow");
                waitv.resize(l+1);
                _RecvSendWaiting *w = &waitv[l];

                w->init(&g, ch);
                w->pdata = cas->data;
                w->ok    = false;
                w->sel_n = n;

                list_add_tail(&w->in_rxtxq, &ch->_sendq);
            }

            // recv
            else if (cas->op == _CHANRECV || cas->op == _CHANRECV_) {
                bool commaok = (cas->op == _CHANRECV_);

                bool ok, done = ch->_tryrecv(cas->data, &ok);
                if (done) {
                    // don't let already queued cases win
                    g.which = "rx prepoll won"; // !NULL    XXX -> current waiter?

                    if (commaok)
                        *cas->rxok = ok;
                    selected = n;
                    break;
                }

                int l = waitv.size();
                if (l >= casec)
                    bug("select: waitv overflow");
                waitv.resize(l+1);
                _RecvSendWaiting *w = &waitv[l];

                w->init(&g, ch);
                w->pdata = cas->data;
                w->ok    = false;
                w->sel_n = n;

                list_add_tail(&w->in_rxtxq, &ch->_recvq);
            }

            // bad case
            else {
                bug("select: invalid op during phase 2");
            }
        ch->_mu.unlock();
    }

    // no case became ready during phase 2 subscribe - wait.
    if (selected == -1) {   // XXX -> just use g.which ?
        g.wait();
        sel = g.which;
        selected = sel.sel_n;
    }

    const _selcase *cas = &casev[selected];
    if (cas->op == _CHANSEND) {
        if (!sel.ok)
            panic("send on closed channel zzz");    // XXX
        return selected;
    }
    else if (cas->op == _CHANRECV || cas->op == _CHANRECV_) {
        bool commaok = (cas->op == _CHANRECV_);

        if (commaok)
            *cas->rxok = sel.ok;
        return selected;
    }
    else {
        bug("select: selected case has invalid op");
    }






#if 0
    // selected returns what was selected in g.
    // the return signature is the one of select.
    def selected():
        g.wait()
        sel = g.which
        if isinstance(sel, _SendWaiting):
            if (!sel.ok)
                panic("send on closed channel");
            return sel->sel_n, None

        if isinstance(sel, _RecvWaiting):
            rx_ = sel.rx_
            if not sel.sel_commaok:
                rx, ok = rx_
                rx_ = rx
            return sel->sel_n, rx_

        raise AssertionError("select: unreachable")

    try:
        for n, ch, tx in sendv:
            ch->_mu.lock();
            with g._mu:
                // a case that we previously queued already won
                if (g.which != NULL) {
                    ch->_mu.unlock()
                    return selected()
                }

                ok = ch->_trysend(tx)
                if ok:
                    // don't let already queued cases win
                    g.which = "tx prepoll won"  // !None

                    return n, None

                w = _SendWaiting(g, ch, tx)
                w.sel_n = n
                ch._sendq.append(w)
            ch->_mu.unlock()

        for n, ch, commaok in recvv:
            ch._mu.lock()
            with g._mu:
                // a case that we previously queued already won
                if (g.which != NULL) {
                    ch._mu.unlock()
                    return selected()
                }

                rx_, ok = ch._tryrecv()
                if ok:
                    // don't let already queued cases win
                    g.which = "rx prepoll won"  // !None

                    if not commaok:
                        rx, ok = rx_
                        rx_ = rx
                    return n, rx_

                w = _RecvWaiting(g, ch)
                w.sel_n = n
                w.sel_commaok = commaok
                ch._recvq.append(w)
            ch._mu.unlock()

        return selected()

    finally:
        // unsubscribe not-succeeded waiters
        g.dequeAll()
#endif
}

// _blockforever blocks current goroutine forever.
void _blockforever() {
    // take a lock twice. It will forever block on the second lock attempt.
    // Under gevent, similarly to Go, this raises "LoopExit: This operation
    // would block forever", if there are no other greenlets scheduled to be run.
    Sema dead;
    dead.acquire();
    dead.acquire();
    bug("_blockforever: woken up");
}

// ---- for tests ----

// _tchanblocked returns whether there are any recevers/senders blocked on the channel.
//
// whether to check receivers and/or senders is controlled by recv/send.
bool _tchanblocked(_chan *ch, bool recv, bool send) {
    bool blocked = false;
    ch->_mu.lock();
    if (recv && !list_empty(&ch->_recvq))
        blocked = true;
    if (send && !list_empty(&ch->_sendq))
        blocked = true;
    ch->_mu.unlock();
    return blocked;
}


// ---- XXX ----

void test() {
    _chan *a = NULL, *b = NULL;
    int tx = 1, arx; bool aok;
    int rx;

    _selcase sel[4];
    sel[0]  = _selsend(a, &tx);
    sel[1]  = _selrecv(b, &rx);
    sel[2]  = _selrecv_(a, &arx, &aok);
    sel[3]  = _default;
    int _ = _chanselect(sel, ARRAY_SIZE(sel));

    if (_ == 0)
        printf("tx\n");
    if (_ == 1)
        printf("rx\n");
    if (_ == 2)
        printf("rx_\n");
    if (_ == 3)
        printf("defaut\n");
}

void testcpp() {
    chan<int> a;
    chan<char[100]> b;
    int i=1, j; bool jok;
    char s[100];

    int _ = select({
        _send(a, &i),           // 0
        _recv(b, &s),           // 1
        _recv_(a, &j, &jok),    // 2
        _default,               // 3
    });

    if (_ == 0)
        printf("tx\n");
    if (_ == 1)
        printf("rx\n");
    if (_ == 2)
        printf("rx_\n");
    if (_ == 3)
        printf("defaut\n");
}

}   // golang::
