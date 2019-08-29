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

// Library Libgolang provides Go-like features for C and C++.
// See libgolang.h for library overview.

// Pygolang C part: provides runtime implementation of panic, channels, etc.
//
// C++ (not C) is used:
// - to implement C-level panic (via C++ exceptions).
// - to provide chan<T> template that can be used as chan[T] in Cython.
// - because Cython (currently ?) does not allow to add methods to `cdef struct`.

#include "golang/libgolang.h"

#include <algorithm>
#include <atomic>
#include <exception>
#include <functional>
#include <limits>
#include <memory>
#include <mutex>        // lock_guard
#include <random>
#include <string>

#include <stdlib.h>
#include <string.h>

// linux/list.h needs ARRAY_SIZE    XXX -> better use c.h or ccan/array_size.h ?
#ifndef ARRAY_SIZE
# define ARRAY_SIZE(A) (sizeof(A) / sizeof((A)[0]))
#endif
#include <linux/list.h>

using std::atomic;
using std::bad_alloc;
using std::exception;
using std::max;
using std::numeric_limits;
using std::string;
using std::unique_ptr;
using std::vector;

namespace golang {

// ---- panic ----

struct PanicError : exception {
    const char *arg;
};

// panic throws exception that represents C-level panic.
// the exception can be caught at C++ level via try/catch and recovered via recover.
[[noreturn]] void panic(const char *arg) {
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

[[noreturn]] void bug(const char *msg) {
    throw Bug(msg);
}

// ---- runtime ----

// initially NULL to crash if runtime was not initialized
static const _libgolang_runtime_ops *_runtime = NULL;

void _libgolang_init(const _libgolang_runtime_ops *runtime_ops) {
    if (_runtime != NULL) // XXX better check atomically
        panic("libgolang: double init");
    _runtime = runtime_ops;
}

void _taskgo(void (*f)(void *), void *arg) {
    _runtime->go(f, arg);
}

void _tasknanosleep(uint64_t dt) {
    _runtime->nanosleep(dt);
}

uint64_t _nanotime() {
    return _runtime->nanotime();
}


// ---- semaphores ----

// Sema provides semaphore.
struct Sema {
    _libgolang_sema *_gsema;

    Sema();
    ~Sema();
    void acquire();
    void release();

private:
    Sema(const Sema&);      // don't copy
};

Sema::Sema() {
    Sema *sema = this;

    sema->_gsema = _runtime->sema_alloc();
    if (!sema->_gsema)
        panic("sema: alloc failed");
}

Sema::~Sema() {
    Sema *sema = this;

    _runtime->sema_free(sema->_gsema);
    sema->_gsema = NULL;
}

void Sema::acquire() {
    Sema *sema = this;
    _runtime->sema_acquire(sema->_gsema);
}

void Sema::release() {
    Sema *sema = this;
    _runtime->sema_release(sema->_gsema);
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

// with_lock mimics `with mu` from python.
#define with_lock(mu) std::lock_guard<Mutex> _with_lock_ ## __COUNTER__ (mu)

// defer(f) mimics defer from golang.
// XXX f is called at end of current scope, not function.
#define defer(f) _deferred _defer_ ## __COUNTER__ (f)
struct _deferred {
    typedef std::function<void(void)> F;
    F f;

    _deferred(F f) : f(f) {}
    ~_deferred() { f(); }
private:
    _deferred(const _deferred&);    // don't copy
};

// ---- channels -----

struct _WaitGroup;
struct _RecvSendWaiting;

// _chan is a raw channel with Go semantic.
//
// Over raw channel the data is sent/received via elemsize'ed memcpy of void*
// and the caller must make sure to pass correct arguments.
//
// See chan<T> for type-safe wrapper.
//
// _chan is not related to Python runtime and works without GIL if libgolang
// runtime works without GIL(*).
//
// (*) for example "thread" runtime works without GIL, while "gevent" runtime
//     acquires GIL on every semaphore acquire.
struct _chan {
    atomic<int> _refcnt;    // reference counter for _chan object
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

    void incref();
    void decref();
    int  refcnt();

    void send(const void *ptx);
    bool recv_(void *prx);
    void recv(void *prx);
    bool _trysend(const void *tx);
    bool _tryrecv(void *prx, bool *pok);
    void close();
    unsigned len();
    unsigned cap();

    void _dataq_append(const void *ptx);
    void _dataq_popleft(void *prx);
private:
    _chan(const _chan&);    // don't copy

    template<bool onstack> void _send2 (const void *);
    void __send2 (const void *, _WaitGroup*, _RecvSendWaiting*);
    template<bool onstack> bool _recv2_(void *);
    bool __recv2_(void *, _WaitGroup*, _RecvSendWaiting*);
};

// _RecvSendWaiting represents a receiver/sender waiting on a chan.
struct _RecvSendWaiting {
    _WaitGroup  *group; // group of waiters this receiver/sender is part of
    _chan       *chan;  // channel receiver/sender is waiting on

    list_head   in_rxtxq; // in recv or send queue of the channel (_chan._recvq|_sendq -> _)

    // recv: on wakeup: sender|closer -> receiver; NULL means "don't copy received value"
    // send: ptr-to data to send
    void    *pdata;
    // on wakeup: whether recv/send succeeded  (send fails on close)
    bool    ok;

    // this wait is used in under select as case #sel_n
    int     sel_n;

    _RecvSendWaiting();
    void init(_WaitGroup *group, _chan *ch);
    void wakeup(bool ok);
private:
    _RecvSendWaiting(const _RecvSendWaiting&);  // don't copy
};

// _WaitGroup is a group of waiting senders and receivers.
//
// Only 1 waiter from the group can succeed waiting.
struct _WaitGroup {
    Sema       _sema;   // used for wakeup

    Mutex      _mu;     // lock    NOTE ∀ chan order is always: chan._mu > ._mu
    // on wakeup: sender|receiver -> group:
    //   .which  _{Send|Recv}Waiting     instance which succeeded waiting.
    const _RecvSendWaiting    *which;

    _WaitGroup();
    bool try_to_win(_RecvSendWaiting *waiter);
    void wait();
    void wakeup();
private:
    _WaitGroup(const _WaitGroup&);  // don't copy
};


// Default _RecvSendWaiting ctor creates zero-value _RecvSendWaiting.
// zero value _RecvSendWaiting is invalid and must be initialized via .init before use.
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
    w->pdata = NULL;
    w->ok    = false;
    w->sel_n = -1;
}

// wakeup notifies waiting receiver/sender that corresponding operation completed.
void _RecvSendWaiting::wakeup(bool ok) {
    _RecvSendWaiting *w = this;
    w->ok = ok;
    w->group->wakeup();
}

_WaitGroup::_WaitGroup() {
    _WaitGroup *group = this;
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
        list_del_init(&w->in_rxtxq); // _init is important as we can try to remove the
                                     // waiter the second time in select.
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
//
// returned channel has refcnt=1.
_chan *_makechan(unsigned elemsize, unsigned size) {
    _chan *ch;
    ch = (_chan *)malloc(sizeof(_chan) + size*elemsize);
    if (ch == NULL)
        return NULL;
    memset((void *)ch, 0, sizeof(*ch));
    new (&ch->_mu) Sema();

    ch->_refcnt   = 1;
    ch->_cap      = size;
    ch->_elemsize = elemsize;
    ch->_closed   = false;

    INIT_LIST_HEAD(&ch->_recvq);
    INIT_LIST_HEAD(&ch->_sendq);

    return ch;
}

// _chanxincref increments reference counter of the channel.
//
// it is noop if ch=nil.
void _chanxincref(_chan *ch) {
    if (ch == NULL)
        return;
    ch->incref();
}
void _chan::incref() {
    _chan *ch = this;

    int refcnt_was = ch->_refcnt.fetch_add(+1);
    if (refcnt_was < 1)
        panic("chan: incref: refcnt was < 1");
}

// _chanxdecref decrements reference counter of the channel.
//
// if refcnt goes to zero, the channel is deallocated.
// it is noop if ch=nil.
void _chanxdecref(_chan *ch) {
    if (ch == NULL)
        return;
    ch->decref();
}
void _chan::decref() {
    _chan *ch = this;

    int refcnt_was = ch->_refcnt.fetch_add(-1);
    if (refcnt_was < 1)
        panic("chan: decref: refcnt was < 1");
    if (refcnt_was != 1)
        return;

    // refcnt=0 -> free the channel
    ch->_mu.~Mutex();
    memset((void *)ch, 0, sizeof(*ch) + ch->_cap*ch->_elemsize);
    free(ch);
}

// _chanrefcnt returns current reference counter of the channel.
//
// NOTE if returned refcnt is > 1, the caller, due to concurrent execution of
// other goroutines, cannot generally assume that the reference counter won't change.
int _chanrefcnt(_chan *ch) {
    return ch->refcnt();
}
int _chan::refcnt() {
    _chan *ch = this;
    return ch->_refcnt;
}


void _blockforever();


// send sends data to a receiver.
//
// sizeof(*ptx) must be ch._elemsize.
void _chansend(_chan *ch, const void *ptx) {
    if (ch == NULL)      // NOTE: cannot do this check in _chan::send
        _blockforever(); // (C++ assumes `this` is never NULL and optimizes it out)
    ch->send(ptx);
}
template<> void _chan::_send2</*onstack=*/true> (const void *ptx);
template<> void _chan::_send2</*onstack=*/false>(const void *ptx);
void _chan::send(const void *ptx) {
    _chan *ch = this;

    ch->_mu.lock();
        bool done = ch->_trysend(ptx);
        if (done)
            return;

        (_runtime->flags & STACK_DEAD_WHILE_PARKED) \
            ? ch->_send2</*onstack=*/false>(ptx)
            : ch->_send2</*onstack=*/true >(ptx);
}

template<> void _chan::_send2</*onstack=*/true> (const void *ptx) {
        _WaitGroup         g;
        _RecvSendWaiting   me;
        __send2(ptx, &g, &me);
}

template<> void _chan::_send2</*onstack=*/false>(const void *ptx) { _chan *ch = this;
        unique_ptr<_WaitGroup>        g  (new _WaitGroup);
        unique_ptr<_RecvSendWaiting>  me (new _RecvSendWaiting);

        // ptx stack -> heap (if ptx is on stack)   TODO avoid copy if ptx is !onstack
        void *ptx_onheap = malloc(ch->_elemsize);
        if (ptx_onheap == NULL) {
            ch->_mu.unlock();
            throw bad_alloc();
        }
        memcpy(ptx_onheap, ptx, ch->_elemsize);
        defer([&]() {
            free(ptx_onheap);
        });

        __send2(ptx_onheap, g.get(), me.get());
}

void _chan::__send2(const void *ptx, _WaitGroup *g, _RecvSendWaiting *me) {  _chan *ch = this;
        me->init(g, ch);
        me->pdata   = (void *)ptx; // we add it to _sendq; the memory will be only read
        me->ok      = false;

        list_add_tail(&me->in_rxtxq, &ch->_sendq);
    ch->_mu.unlock();

    g->wait();
    if (g->which != me)
        bug("chansend: g.which != me");
    if (!me->ok)
        panic("send on closed channel");
}

// recv_ is "comma-ok" version of recv.
//
// ok is true - if receive was delivered by a successful send.
// ok is false - if receive is due to channel being closed and empty.
//
// sizeof(*prx) must be ch._elemsize | prx=NULL.
bool _chanrecv_(_chan *ch, void *prx) {
    if (ch == NULL)
        _blockforever();
    return ch->recv_(prx);
}
template<> bool _chan::_recv2_</*onstack=*/true> (void *prx);
template<> bool _chan::_recv2_</*onstack=*/false>(void *prx);
bool _chan::recv_(void *prx) { // -> ok
    _chan *ch = this;

    ch->_mu.lock();
        bool ok, done = ch->_tryrecv(prx, &ok);
        if (done)
            return ok;

        return (_runtime->flags & STACK_DEAD_WHILE_PARKED) \
            ? ch->_recv2_</*onstack=*/false>(prx)
            : ch->_recv2_</*onstack=*/true> (prx);
}

template<> bool _chan::_recv2_</*onstack=*/true> (void *prx) {
        _WaitGroup         g;
        _RecvSendWaiting   me;
        return __recv2_(prx, &g, &me);
}

template<> bool _chan::_recv2_</*onstack=*/false>(void *prx) {  _chan *ch = this;
        unique_ptr<_WaitGroup>        g  (new _WaitGroup);
        unique_ptr<_RecvSendWaiting>  me (new _RecvSendWaiting);

        if (prx == NULL)
            return __recv2_(prx, g.get(), me.get());

        // prx stack -> onheap + copy back (if prx is on stack) TODO avoid copy if prx is !onstack
        void *prx_onheap = malloc(ch->_elemsize);
        if (prx_onheap == NULL) {
            ch->_mu.unlock();
            throw bad_alloc();
        }
        defer([&]() {
            free(prx_onheap);
        });

        bool ok = __recv2_(prx_onheap, g.get(), me.get());
        memcpy(prx, prx_onheap, ch->_elemsize);
        return ok;
}

bool _chan::__recv2_(void *prx, _WaitGroup *g, _RecvSendWaiting *me) {  _chan *ch = this;
        me->init(g, ch);
        me->pdata   = prx;
        me->ok      = false;
        list_add_tail(&me->in_rxtxq, &ch->_recvq);
    ch->_mu.unlock();

    g->wait();
    if (g->which != me)
        bug("chanrecv: g.which != me");
    return me->ok;
}

// recv receives from the channel.
//
// if prx != NULL received value is put into *prx.
void _chanrecv(_chan *ch, void *prx) {
    if (ch == NULL)
        _blockforever();
    ch->recv(prx);
}
void _chan::recv(void *prx) {
    _chan *ch = this;
    (void)ch->recv_(prx);
    return;
}


// _trysend(ch, *ptx) -> done
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
        if (recv->pdata != NULL)
            memcpy(recv->pdata, ptx, ch->_elemsize);
        recv->wakeup(/*ok=*/true);
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
            recv->wakeup(/*ok=*/true);
        } else {
            ch->_mu.unlock();
        }
        return true;
    }
}


// _tryrecv() -> (*prx, *pok), done
//
// must be called with ._mu held.
// if done or panic - returns with ._mu released.
// if !done - returns with ._mu still being held.
//
// if !done - (*prx, *pok) are left unmodified.
// if prx=NULL received value is not copied into *prx.
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
            send->wakeup(/*ok=*/true);
        } else {
            ch->_mu.unlock();
        }

        return true;
    }

    // closed
    if (ch->_closed) {
        ch->_mu.unlock();
        if (prx != NULL)
            memset(prx, 0, ch->_elemsize);
        *pok = false;
        return true;
    }

    // sync | empty: there is waiting writer
    _RecvSendWaiting *send = _dequeWaiter(&ch->_sendq);
    if (send == NULL)
        return false;

    ch->_mu.unlock();
    if (prx != NULL)
        memcpy(prx, send->pdata, ch->_elemsize);
    *pok = true;
    send->wakeup(/*ok=*/true);
    return true;
}

// close closes sending side of the channel.
void _chanclose(_chan *ch) {
    if (ch == NULL)
        panic("close of nil channel");
    ch->close();
}
void _chan::close() {
    _chan *ch = this;

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
            if (recv->pdata != NULL)
                memset(recv->pdata, 0, ch->_elemsize);
            recv->wakeup(/*ok=*/false);
            ch->_mu.lock();
        }

        // wake-up all writers (they will panic)
        while (1) {
            _RecvSendWaiting *send = _dequeWaiter(&ch->_sendq);
            if (send == NULL)
                break;

            ch->_mu.unlock();
            send->wakeup(/*ok=*/false);
            ch->_mu.lock();
        }
    ch->_mu.unlock();
}

// len returns current number of buffered elements.
unsigned _chanlen(_chan *ch) {
    if (ch == NULL)
        return 0; // len(nil) = 0
    return ch->len();
}
unsigned _chan::len() {
    _chan *ch = this;

    ch->_mu.lock(); // only to make valgrind happy
    unsigned len = ch->_dataq_n;
    ch->_mu.unlock();
    return len;
}

// cap returns channel capacity.
unsigned _chancap(_chan *ch) {
    if (ch == NULL)
        return 0; // cap(nil) = 0
    return ch->cap();
}
unsigned _chan::cap() {
    _chan *ch = this;
    return ch->_cap;
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
// if prx=NULL the element is popped, but not copied anywhere.
void _chan::_dataq_popleft(void *prx) {
    _chan *ch = this;

    if (ch->_dataq_n == 0)
        bug("chan: dataq.popleft on empty dataq");
    if (ch->_dataq_r >= ch->_cap)
        bug("chan: dataq.popleft: r >= cap");

    if (prx != NULL)
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

static const _RecvSendWaiting _sel_txrx_prepoll_won;
template<bool onstack> static int _chanselect2(const _selcase *, int, const vector<int>&);
template<> int _chanselect2</*onstack=*/true> (const _selcase *, int, const vector<int>&);
template<> int _chanselect2</*onstack=*/false>(const _selcase *, int, const vector<int>&);
static int __chanselect2(const _selcase *, int, const vector<int>&, _WaitGroup*);

// _chanselect executes one ready send or receive channel case.
//
// if no case is ready and default case was provided, select chooses default.
// if no case is ready and default was not provided, select blocks until one case becomes ready.
//
// returns: selected case number.
//
// For example:
//
//      _selcase sel[4];
//      sel[0]  = _selsend(chi, &i);
//      sel[1]  = _selrecv(chp, &p);
//      sel[2]  = _selrecv_(chi, &j, &jok);
//      sel[3]  = _default;
//      _ = _chanselect(sel, 4);
//
// See `select` for user-friendly wrapper.
// NOTE casev is not modified and can be used for next _chanselect calls.
int _chanselect(const _selcase *casev, int casec) {
    if (casec < 0)
        panic("select: casec < 0");

    // select promise: if multiple cases are ready - one will be selected randomly
    vector<int> nv(casec); // n -> n(case)      TODO -> caller stack-allocate nv
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
        else if (cas->op == _CHANRECV) {
            if (ch != NULL) {   // nil chan is never ready
                ch->_mu.lock();
                if (1) {
                    bool ok, done = ch->_tryrecv(cas->data, &ok);
                    if (done) {
                        if (cas->rxok != NULL)
                            *cas->rxok = ok;
                        return n;
                    }
                }
                ch->_mu.unlock();
                havenonnil = true;
            }
        }

        // bad
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
    return (_runtime->flags & STACK_DEAD_WHILE_PARKED) \
        ? _chanselect2</*onstack=*/false>(casev, casec, nv)
        : _chanselect2</*onstack=*/true> (casev, casec, nv);
}

template<> int _chanselect2</*onstack=*/true> (const _selcase *casev, int casec, const vector<int>& nv) {
    _WaitGroup  g;
    return __chanselect2(casev, casec, nv, &g);
}

template<> int _chanselect2</*onstack=*/false>(const _selcase *casev, int casec, const vector<int>& nv) {
    unique_ptr<_WaitGroup>  g (new _WaitGroup);
    int i;
    unsigned rxmax=0, txtotal=0;

    // reallocate chan .tx / .rx to heap; adjust casev
    // XXX avoid doing this if all .tx and .rx are on heap?
    unique_ptr<_selcase[]>  casev_onheap (new _selcase[casec]);
    for (i = 0; i < casec; i++) {
        const _selcase *cas = &casev[i];
        casev_onheap[i] = *cas;
        if (cas->ch == NULL) // nil chan
            continue;
        if (cas->op == _CHANSEND) {
            txtotal += cas->ch->_elemsize;
        }
        else if (cas->op == _CHANRECV) {
            rxmax = max(rxmax, cas->ch->_elemsize);
        }
        else {
            bug("select: invalid op  ; _chanselect2: !onstack: A");
        }
    }

    // tx are appended sequentially; all rx go to &rxtxdata[0]
    char *rxtxdata = (char *)malloc(max(rxmax, txtotal));
    if (rxtxdata == NULL)
        throw bad_alloc();
    defer([&]() {
        free(rxtxdata);
    });

    char *ptx = rxtxdata;
    for (i = 0; i <casec; i++) {
        _selcase *cas = &casev_onheap[i];
        if (cas->ch == NULL) // nil chan
            continue;
        if (cas->op == _CHANSEND) {
            memcpy(ptx, cas->data, cas->ch->_elemsize);
            cas->data = ptx;
            ptx += cas->ch->_elemsize;
        }
        else if (cas->op == _CHANRECV) {
            cas->data = rxtxdata;
        } else {
            bug("select: invalid op  ; _chanselect2: !onstack: B");
        }
    }

    // select ...
    int selected = __chanselect2(casev_onheap.get(), casec, nv, g.get());

    // copy data back to original rx location.
    _selcase *cas = &casev_onheap[selected];
    if (cas->op == _CHANRECV) {
        const _selcase *cas0 = &casev[selected];
        if (cas0->data != NULL)
            memcpy(cas0->data, cas->data, cas->ch->_elemsize);
    }

    return selected;
}

static int __chanselect2(const _selcase *casev, int casec, const vector<int>& nv, _WaitGroup* g) {
    // storage for waiters we create    XXX stack-allocate (if !STACK_DEAD_WHILE_PARKED)
    //  XXX or let caller stack-allocate? but then we force it to know sizeof(_RecvSendWaiting)
    _RecvSendWaiting *waitv = (_RecvSendWaiting *)calloc(sizeof(_RecvSendWaiting), casec);
    int               waitc = 0;
    if (waitv == NULL)
        throw bad_alloc();
    // on exit: remove all registered waiters from their wait queues.
    defer([&]() {
        for (int i = 0; i < waitc; i++) {
            _RecvSendWaiting *w = &waitv[i];
            w->chan->_mu.lock();
            list_del_init(&w->in_rxtxq); // thanks to _init used in _dequeWaiter
            w->chan->_mu.unlock();       // it is ok to del twice even if w was already removed
        }

        free(waitv);
        waitv = NULL;
    });


    for (auto n : nv) {
        const _selcase *cas = &casev[n];
        _chan *ch = cas->ch;

        if (ch == NULL) // nil chan is never ready
            continue;

        ch->_mu.lock();
        with_lock(g->_mu); // with, because _trysend may panic
            // a case that we previously queued already won while we were
            // queuing other cases.
            if (g->which != NULL) {
                ch->_mu.unlock();
                goto ready;
            }

            // send
            if (cas->op == _CHANSEND) {
                bool done = ch->_trysend(cas->data);
                if (done) {
                    g->which = &_sel_txrx_prepoll_won; // !NULL not to let already queued cases win
                    return n;
                }

                if (waitc >= casec)
                    bug("select: waitv overflow");
                _RecvSendWaiting *w = &waitv[waitc++];

                w->init(g, ch);
                w->pdata = cas->data;
                w->ok    = false;
                w->sel_n = n;

                list_add_tail(&w->in_rxtxq, &ch->_sendq);
            }

            // recv
            else if (cas->op == _CHANRECV) {
                bool ok, done = ch->_tryrecv(cas->data, &ok);
                if (done) {
                    g->which = &_sel_txrx_prepoll_won; // !NULL not to let already queued cases win
                    if (cas->rxok != NULL)
                        *cas->rxok = ok;
                    return n;
                }

                if (waitc >= casec)
                    bug("select: waitv overflow");
                _RecvSendWaiting *w = &waitv[waitc++];

                w->init(g, ch);
                w->pdata = cas->data;
                w->ok    = false;
                w->sel_n = n;

                list_add_tail(&w->in_rxtxq, &ch->_recvq);
            }

            // bad
            else {
                bug("select: invalid op during phase 2");
            }
        ch->_mu.unlock();
    }

    // wait for a case to become ready
    g->wait();
ready:
    if (g->which == &_sel_txrx_prepoll_won)
        bug("select: woke up with g.which=_sel_txrx_prepoll_won");

    const _RecvSendWaiting *sel = g->which;
    int selected = sel->sel_n;
    const _selcase *cas = &casev[selected];
    if (cas->op == _CHANSEND) {
        if (!sel->ok)
            panic("send on closed channel");
        return selected;
    }
    else if (cas->op == _CHANRECV) {
        if (cas->rxok != NULL)
            *cas->rxok = sel->ok;
        return selected;
    }

    bug("select: selected case has invalid op");
}

// _blockforever blocks current goroutine forever.
void (*_tblockforever)() = NULL;
void _blockforever() {
    if (_tblockforever != NULL)
        _tblockforever();
    // take a lock twice. It will forever block on the second lock attempt.
    // Under gevent, similarly to Go, this raises "LoopExit: This operation
    // would block forever", if there are no other greenlets scheduled to be run.
    Sema dead;
    dead.acquire();
    dead.acquire();
    bug("_blockforever: woken up");
}

// ---- for tests ----

// _tchanlenrecvqlen returns len(_ch._recvq)
int _tchanrecvqlen(_chan *_ch) {
    int l = 0;
    list_head *h;
    _ch->_mu.lock();
    list_for_each(h, &_ch->_recvq)
        l++;
    _ch->_mu.unlock();
    return l;
}

// _tchanlensendqlen returns len(_ch._sendq)
int _tchansendqlen(_chan *_ch) {
    int l = 0;
    list_head *h;
    _ch->_mu.lock();
    list_for_each(h, &_ch->_sendq)
        l++;
    _ch->_mu.unlock();
    return l;
}

}   // golang::


// ---- golang::time:: ----

namespace golang {
namespace time {

void sleep(double dt) {
    if (dt <= 0)
        dt = 0;
    dt *= 1E9; // s -> ns
    if (dt > numeric_limits<uint64_t>::max())
        panic("sleep: dt overflow");
    uint64_t dt_ns = dt;
    _tasknanosleep(dt_ns);
}

double now() {
    uint64_t t_ns = _nanotime();
    double t_s = t_ns * 1E-9;   // no overflow possible
    return t_s;
}

}}  // golang::time::
