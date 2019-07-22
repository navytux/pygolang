# -*- coding: utf-8 -*-
# cython: language_level=2
# cython: binding=True
# distutils: language = c++
# distutils: include_dirs = ../3rdparty/include
# distutils: sources = golang.cpp
# distutils: depends = golang.h
#
# Copyright (C) 2018-2019  Nexedi SA and Contributors.
#                          Kirill Smelkov <kirr@nexedi.com>
#
# This program is free software: you can Use, Study, Modify and Redistribute
# it under the terms of the GNU General Public License version 3, or (at your
# option) any later version, as published by the Free Software Foundation.
#
# You can also Link and Combine this program with other software covered by
# the terms of any of the Free Software licenses or any of the Open Source
# Initiative approved licenses and Convey the resulting work. Corresponding
# source of such a combination shall include the source code for all other
# software used.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# See COPYING file for full licensing terms.
# See https://www.nexedi.com/licensing for rationale and options.

from __future__ import print_function, absolute_import

from libc.stdlib cimport malloc, free
from libc.string cimport memset
from libcpp.vector cimport vector

"""
#cdef extern from "../3rdparty/include/linux/list.h":
cdef:
    struct list_head:
        list_head *next
        list_head *prev
"""

cdef extern from *:
    ctypedef bint cbool "bool"


cdef extern from "golang.h" nogil:
    void panic(const char *)
    const char *recover() except +
    void bug(const char *)

    struct _chan
    cppclass chan[T]:
        _chan *_ch
        chan();
        #void send(T *ptx)
        void send(T tx)
        bint recv_(T *prx)
        void recv(T *prx)
        void close()
        unsigned len()
    chan[T] makechan[T](unsigned size) except +

    enum _chanop:
        _CHANSEND
        _CHANRECV
        _CHANRECV_
        _DEFAULT
    struct _selcase:
        _chanop op
        void    *data

    # XXX not sure how to wrap select
    int _chanselect(const _selcase *casev, int casec) except +

    _selcase _send[T](chan[T] ch, T tx)
    _selcase _recv[T](chan[T] ch, T* prx)
    _selcase _recv_[T](chan[T] ch, T* prx, bint *pok)
    const _selcase _default


# ---- channels ----

# XXX nogil globally?

"""
cdef struct _WaitGroup

# chan is a channel with Go semantic.
cdef struct chan:
    unsigned    _cap        # channel capacity (elements)
    unsigned    _elemsize   # size of element

    # ._mu          lock                                    XXX -> _OSMutex (that can synchronize in between Procs) ?
    # ._dataq       deque *: data buffer                    XXX -> [_cap*_elemsize]
    list_head   _recvq      # blocked receivers _ -> _RecvSendWaiting.XXX
    list_head   _sendq      # blocked senders   _ -> _RecvSendWaiting.XXX
    bint        _closed

# _RecvSendWaiting represents a receiver/sender waiting on a chan.
cdef struct _RecvSendWaiting:
    _WaitGroup  *group  # group of waiters this receiver/sender is part of
    chan        *chan   # channel receiver/sender is waiting on

    # XXX + op

    # recv: on wakeup: sender|closer -> receiver
    # send: ptr-to data to send
    void    *pdata
    # on wakeup: whether recv/send succeeded  (send fails on close)
    bint    ok

# _WaitGroup is a group of waiting senders and receivers.
#
# Only 1 waiter from the group can succeed waiting.
cdef struct _WaitGroup:
    # ._waitv   [] of _{Send|Recv}Waiting
    # ._sema    semaphore   used for wakeup
    #
    # ._mu      lock    NOTE ∀ chan order is always: chan._mu > ._mu
    #
    # on wakeup: sender|receiver -> group:
    #   .which  _{Send|Recv}Waiting     instance which succeeded waiting.
    _RecvSendWaiting    *which

# _dequeWaiter dequeues a send or recv waiter from a channel's _recvq or _sendq.
#
# the channel owning {_recv|_send}q must be locked.
cdef _RecvSendWaiting *_dequeWaiter(list_head *queue) nogil:
    return NULL

#IF 0
#    while len(queue) > 0:
#        w = queue.popleft()
#        # if this waiter can win its group - return it.
#        # if not - someone else from its group already has won, and so we anyway have
#        # to remove the waiter from the queue.
#        if w.group.try_to_win(w):
#            return w
#
#    return None
####


# makechan creates new chan<elemsize>(size).
cdef chan *makechan(unsigned elemsize, unsigned size) nogil:
    cdef chan *ch
    ch = <chan *>malloc(sizeof(chan) + size*elemsize)
    if ch == NULL:
        return NULL
    memset(ch, 0, sizeof(ch[0]))

    ch._cap      = size
    ch._elemsize = elemsize
    ch._closed   = False

    return ch


# # chaninit initializes chan<elemsize>(size).
# cdef void chaninit(chan *ch, unsigned elemsize, unsigned size) nogil:
#     ch._cap      = size
#     ch._elemsize = elemsize
#     ch._closed   = False
#
#     # XXX alloc _dataq
#     # XXX ._recvq = NULL
#     # XXX ._sendq = NULL

# chansend sends data to a receiver.
#
# sizeof(*ptx) must be ch._elemsize | ptx=NULL.
cdef void chansend(chan *ch, void *ptx) nogil:
    if ch is NULL:
        _blockforever()

    cdef _WaitGroup         g
    cdef _RecvSendWaiting   me

    #ch._mu.acquire()
    if 1:
        ok = _trysend(ch, ptx)
        if ok:
            return

        g.which     = NULL
        me.group    = &g
        me.chan     = ch
        me.pdata    = ptx
        me.ok       = False
        #g._waitv.append(me)
        #ch._sendq.append(me)

    #ch._mu.release()

    waitgroup(&g)
    if not (g.which is &me):
        bug("chansend: g.which != me")
    if not me.ok:
        panic("send on closed channel")


# chanrecv_ is "comma-ok" version of chanrecv.
#
# ok is true - if receive was delivered by a successful send.
# ok is false - if receive is due to channel being closed and empty.
cdef bint chanrecv_(chan *ch, void *prx) nogil: # -> ok
    if ch is NULL:
        _blockforever()

    cdef _WaitGroup         g
    cdef _RecvSendWaiting   me

    #ch._mu.acquire()
    if 1:
        ok = _tryrecv(ch, prx)
        if ok:
            return ok

        g.which     = NULL
        me.group    = &g
        me.chan     = ch
        me.pdata    = prx
        me.ok       = False
        #g._waitv.append(me)
        #ch._recvq.append(me)

    #ch._mu.release()

    waitgroup(&g)
    if not (g.which is &me):
        bug("chanrecv: g.which != me")
    return me.ok

# chanrecv receives from the channel.
#
# received value is put into *prx.
cdef void chanrecv(chan *ch, void *prx) nogil:
    _ = chanrecv_(ch, prx)
    return

# _trysend(ch, obj) -> ok
#
# must be called with ._mu held.
# if ok or panic - returns with ._mu released.
# if !ok - returns with ._mu still being held.
cdef bint _trysend(chan *ch, void *tx) nogil:
    if ch._closed:
        #ch._mu.release()
        panic("send on closed channel")

    # synchronous channel
    if ch._cap == 0:
        recv = _dequeWaiter(&ch._recvq)
        if recv is NULL:
            return False

        #ch._mu.release()
        # XXX copy tx -> recv.data
        #recv.wakeup(obj, True)
        group_wakeup(recv.group)
        return True

#IF 0:   # _trysend
#    # buffered channel
#    else:
#        if len(ch._dataq) >= ch._cap:
#            return False
#
#        ch._dataq.append(obj)
#        recv = _dequeWaiter(ch._recvq)
#        ch._mu.release()
#        if recv is not None:
#            rx = ch._dataq.popleft()
#            recv.wakeup(rx, True)
#        return True
#####

# _tryrecv() -> rx_=(rx, ok), ok        XXX
#
# must be called with ._mu held.
# if ok or panic - returns with ._mu released.
# if !ok - returns with ._mu still being held.
cdef bint _tryrecv(chan *ch, void *prx) nogil: # -> ok
    return False

IF 0:   # _tryrecv
    # buffered
    if len(ch._dataq) > 0:
        rx = ch._dataq.popleft()

        # wakeup a blocked writer, if there is any
        send = _dequeWaiter(ch._sendq)
        ch._mu.release()
        if send is not None:
            ch._dataq.append(send.obj)
            send.wakeup(True)

        return (rx, True), True

    # closed
    if ch._closed:
        ch._mu.release()
        return (None, False), True

    # sync | empty: there is waiting writer
    send = _dequeWaiter(ch._sendq)
    if send is None:
        return (None, False), False

    ch._mu.release()
    rx = send.obj
    send.wakeup(True)
    return (rx, True), True
####

# chanclose closes sending side of the channel.
cdef void chanclose(chan *ch) nogil:
    if ch is NULL:
        panic("close of nil channel")

    # XXX stub
    if ch._closed:
        panic("close of closed channel")
    ch._closed = True

IF 0:   # chanclose
    recvv = []
    sendv = []

    with ch._mu:
        if ch._closed:
            panic("close of closed channel")
        ch._closed = True

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
        recv.wakeup(None, False)
    for send in sendv:
        send.wakeup(False)
####

# chanlen returns current number of buffered elements.
cdef unsigned chanlen(chan *ch) nogil:
    panic("TODO")

"""













IF 0:   # _RecvWaiting
    def __init__(self, group, ch):
        self.group = group
        self.chan  = ch
        group.register(self)

    # wakeup notifies waiting receiver that recv_ completed.
    cdef wakeup(self, rx, ok):
        self.rx_ = (rx, ok)
        self.group.wakeup()
####


IF 0:   # _SendWaiting
    def __init__(self, group, ch, obj):
        self.group = group
        self.chan  = ch
        self.obj   = obj
        group.register(self)

    # wakeup notifies waiting sender that send completed.
    def wakeup(self, ok):
        self.ok = ok
        self.group.wakeup()
####


IF 0:   # _WaitGroup
    def __init__(self):
        self._waitv = []
        self._sema  = threading.Lock()   # in python it is valid to release lock from another thread.
        self._sema.acquire()
        self._mu    = threading.Lock()
        self.which  = None

    def register(self, wait):
        self._waitv.append(wait)

    # try_to_win tries to win waiter after it was dequeued from a channel's {_send|_recv}q.
    #
    # -> ok: true if won, false - if not.
    def try_to_win(self, waiter):
        with self._mu:
            if self.which is not None:
                return False
            else:
                self.which = waiter
                return True

"""
# waitgroup waits for winning case of group to complete.
# XXX -> group_wait ?
cdef void waitgroup(_WaitGroup *group) nogil:
    #group._sema.acquire()  XXX
    pass

# group_wakeup wakes up the group.
#
# prior to wakeup try_to_win must have been called.
# in practice this means that waiters queued to chan.{_send|_recv}q must
# be dequeued with _dequeWaiter.
cdef void group_wakeup(_WaitGroup *group) nogil:
    if group.which is not NULL:
        bug("group_wakeup: group.which=nil")
    #self._sema.release()
"""

IF 0:   # _WaitGroup
    # dequeAll removes all registered waiters from their wait queues.
    def dequeAll(self):
        for w in self._waitv:
            ch = w.chan
            if isinstance(w, _SendWaiting):
                queue = ch._sendq
            else:
                assert isinstance(w, _RecvWaiting)
                queue = ch._recvq

            with ch._mu:
                try:
                    queue.remove(w)
                except ValueError:
                    pass
####

"""
# selcase represents one select case.
cdef struct selcase:
    void (*op)(chan *, void *) nogil    # chansend/chanrecv/default
    void *data                          # chansend: tx; chanrecv: rx
    bint ok                             # comma-ok for rx

# default represents default case for select.
cdef void default(chan *_, void *__) nogil:
    panic("default must not be called")

# chanselect executes one ready send or receive channel case.
#
# if no case is ready and default case was provided, select chooses default.
# if no case is ready and default was not provided, select blocks until one case becomes ready.
#
# returns: selected case number and receive info (None if send case was selected).
#
# example:
#
#   _, _rx = select(
#       ch1.recv,           # 0
#       ch2.recv_,          # 1
#       (ch2.send, obj2),   # 2
#       default,            # 3
#   )
#   if _ == 0:
#       # _rx is what was received from ch1
#       ...
#   if _ == 1:
#       # _rx is (rx, ok) of what was received from ch2
#       ...
#   if _ == 2:
#       # we know obj2 was sent to ch2
#       ...
#   if _ == 3:
#       # default case
#       ...
#
# XXX try to use `...` and kill casec
cdef int chanselect(selcase *casev, int casec) nogil:
    1/0
IF 0:
    # select promise: if multiple cases are ready - one will be selected randomly
    ncasev = list(enumerate(casev))
    random.shuffle(ncasev)

    # first pass: poll all cases and bail out in the end if default was provided
    recvv = [] # [](n, ch, commaok)
    sendv = [] # [](n, ch, tx)
    ndefault = None
    for (n, case) in ncasev:
        # default: remember we have it
        if case is default:
            if ndefault is not None:
                panic("select: multiple default")
            ndefault = n

        # send
        elif isinstance(case, tuple):
            send, tx = case
            if im_class(send) is not chan:
                panic("select: send on non-chan: %r" % (im_class(send),))
            if send.__func__ is not _chan_send:
                panic("select: send expected: %r" % (send,))

            ch = send.__self__
            if ch is not nilchan:   # nil chan is never ready
                ch._mu.acquire()
                if 1:
                    ok = ch._trysend(tx)
                    if ok:
                        return n, None
                ch._mu.release()

                sendv.append((n, ch, tx))

        # recv
        else:
            recv = case
            if im_class(recv) is not chan:
                panic("select: recv on non-chan: %r" % (im_class(recv),))
            if recv.__func__ is _chan_recv:
                commaok = False
            elif recv.__func__ is _chan_recv_:
                commaok = True
            else:
                panic("select: recv expected: %r" % (recv,))

            ch = recv.__self__
            if ch is not nilchan:   # nil chan is never ready
                ch._mu.acquire()
                if 1:
                    rx_, ok = ch._tryrecv()
                    if ok:
                        if not commaok:
                            rx, ok = rx_
                            rx_ = rx
                        return n, rx_
                ch._mu.release()

                recvv.append((n, ch, commaok))

    # execute default if we have it
    if ndefault is not None:
        return ndefault, None

    # select{} or with nil-channels only -> block forever
    if len(recvv) + len(sendv) == 0:
        _blockforever()

    # second pass: subscribe and wait on all rx/tx cases
    g = _WaitGroup()

    # selected returns what was selected in g.
    # the return signature is the one of select.
    def selected():
        g.wait()
        sel = g.which
        if isinstance(sel, _SendWaiting):
            if not sel.ok:
                panic("send on closed channel")
            return sel.sel_n, None

        if isinstance(sel, _RecvWaiting):
            rx_ = sel.rx_
            if not sel.sel_commaok:
                rx, ok = rx_
                rx_ = rx
            return sel.sel_n, rx_

        raise AssertionError("select: unreachable")

    try:
        for n, ch, tx in sendv:
            ch._mu.acquire()
            with g._mu:
                # a case that we previously queued already won
                if g.which is not None:
                    ch._mu.release()
                    return selected()

                ok = ch._trysend(tx)
                if ok:
                    # don't let already queued cases win
                    g.which = "tx prepoll won"  # !None

                    return n, None

                w = _SendWaiting(g, ch, tx)
                w.sel_n = n
                ch._sendq.append(w)
            ch._mu.release()

        for n, ch, commaok in recvv:
            ch._mu.acquire()
            with g._mu:
                # a case that we previously queued already won
                if g.which is not None:
                    ch._mu.release()
                    return selected()

                rx_, ok = ch._tryrecv()
                if ok:
                    # don't let already queued cases win
                    g.which = "rx prepoll won"  # !None

                    if not commaok:
                        rx, ok = rx_
                        rx_ = rx
                    return n, rx_

                w = _RecvWaiting(g, ch)
                w.sel_n = n
                w.sel_commaok = commaok
                ch._recvq.append(w)
            ch._mu.release()

        return selected()

    finally:
        # unsubscribe not-succeeded waiters
        g.dequeAll()
####

# _blockforever blocks current goroutine forever.
cdef void _blockforever() nogil:
    1/0     # XXX stub
IF 0:
    # take a lock twice. It will forever block on the second lock attempt.
    # Under gevent, similarly to Go, this raises "LoopExit: This operation
    # would block forever", if there are no other greenlets scheduled to be run.
    dead = threading.Lock()
    dead.acquire()
    dead.acquire()
####

"""

# ---- python interface ----

from cpython cimport PyObject, Py_INCREF, Py_DECREF

# pydefault represents default case for pyselect.
pydefault  = object()

# pynilchan is the nil py channel.
#
# On nil channel: send/recv block forever; close panics.
cdef pychan nilchan = pychan()
free(nilchan.ch._ch)  # XXX vs _ch being shared_ptr ? XXX -> chanfree (free sema)
nilchan.ch._ch = NULL
pynilchan = nilchan

ctypedef PyObject *pPyObject # https://github.com/cython/cython/issues/534

# pychan is chan<object>
cdef class pychan:
    cdef chan[pPyObject] ch

    def __cinit__(pych, size=0):
        pych.ch = makechan[pPyObject](size)

    # send sends object to a receiver.
    def send(pych, obj):
        # increment obj reference count so that obj stays alive until recv
        # wakes up - e.g. even if send wakes up earlier and returns / drops obj reference.
        #
        # in other words: we send to recv obj and 1 reference to it.
        Py_INCREF(obj)

        with nogil:
            chansend_pyexc(pych.ch, <PyObject *>obj)

    # recv_ is "comma-ok" version of recv.
    #
    # ok is true - if receive was delivered by a successful send.
    # ok is false - if receive is due to channel being closed and empty.
    def recv_(pych): # -> (rx, ok)
        cdef PyObject *_rx = NULL
        cdef bint ok

        with nogil:
            ok = chanrecv__pyexc(pych.ch, &_rx)

        if not ok:
            return (None, ok)

        # we received the object and 1 reference to it.
        rx = <object>_rx    # increfs again
        Py_DECREF(rx)       # since <object> convertion did incref
        return (rx, ok)

    # recv receives from the channel.
    def recv(pych): # -> rx
        rx, _ = pych.recv_()
        return rx

    # close closes sending side of the channel.
    def close(pych):
        chanclose_pyexc(pych.ch)

    def __len__(pych):
        return chanlen_pyexc(pych.ch)

    def __repr__(pych):
        if pych.ch._ch == NULL:
            return "nilchan"
        else:
            return super(pychan, pych).__repr__()


# XXX panic: place = ?

cdef class _PanicError(Exception):
    pass

# panic stops normal execution of current goroutine.
def pypanic(arg):
    raise _PanicError(arg)

# _topyexc converts C-level panic/exc to python panic/exc
cdef void _topyexc() except *:
    # recover is declared `except +` - if it was another - not panic -
    # exception, it will be converted to py exc by cython automatically.
    arg = recover()
    if arg != NULL:
        pypanic(arg)

#cdef void chansend_pyexc(chan[pPyObject] ch, PyObject **_pobj)  nogil except +_topyexc:
#    ch.send(_pobj)
cdef void chansend_pyexc(chan[pPyObject] ch, PyObject *_obj)    nogil except +_topyexc:
    ch.send(_obj)
cdef bint chanrecv__pyexc(chan[pPyObject] ch, PyObject **_prx)  nogil except +_topyexc:
    return ch.recv_(_prx)
cdef void chanclose_pyexc(chan[pPyObject] ch)                   nogil except +_topyexc:
    ch.close()
cdef unsigned chanlen_pyexc(chan[pPyObject] ch)                 nogil except +_topyexc:
    return ch.len()


# pyselect executes one ready send or receive channel case.
#
# if no case is ready and default case was provided, select chooses default.
# if no case is ready and default was not provided, select blocks until one case becomes ready.
#
# returns: selected case number and receive info (None if send case was selected).
#
# example:
#
#   _, _rx = select(
#       ch1.recv,           # 0
#       ch2.recv_,          # 1
#       (ch2.send, obj2),   # 2
#       default,            # 3
#   )
#   if _ == 0:
#       # _rx is what was received from ch1
#       ...
#   if _ == 1:
#       # _rx is (rx, ok) of what was received from ch2
#       ...
#   if _ == 2:
#       # we know obj2 was sent to ch2
#       ...
#   if _ == 3:
#       # default case
#       ...
def pyselect(*pycasev):
    cdef int i, n = len(pycasev), selected
    cdef vector[_selcase] casev = vector[_selcase](n)
    cdef pychan pych
    cdef pPyObject _rx = NULL
    cdef cbool rxok = False
    cdef bint commaok

    # prepare casev for chanselect
    for i in range(n):
        case = pycasev[i]
        # default
        if case is pydefault:
            casev[i] = _default

        # send
        elif isinstance(case, tuple):
            send, tx = case
            if im_class(send) is not pychan:
                pypanic("pyselect: send on non-chan: %r" % (im_class(send),))
            if send.__func__ is not _pychan_send:
                pypanic("pyselect: send expected: %r" % (send,))

            pych = send.__self__
            # incref tx; we'll decref it if it won't be sent.
            # see pychan.send for details
            Py_INCREF(tx)
            casev[i] = _send(pych.ch, <pPyObject>tx)

        # recv
        else:
            recv = case
            if im_class(recv) is not pychan:
                pypanic("pyselect: recv on non-chan: %r" % (im_class(recv),))
            if recv.__func__ is _pychan_recv:
                commaok = False
            elif recv.__func__ is _pychan_recv_:
                commaok = True
            else:
                pypanic("pyselect: recv expected: %r" % (recv,))

            pych = recv.__self__
            if commaok:
                casev[i] = _recv_(pych.ch, &_rx, &rxok)
            else:
                casev[i] = _recv(pych.ch, &_rx)

    with nogil:
        #selected = select(casev)    # XXX c++ exc
        selected = _chanselect(&casev[0], casev.size())

    # decref not sent tx (see ^^^ send prepare)
    for i in range(n):
        if casev[i].op == _CHANSEND and (i != selected):
            p_tx = <PyObject **>casev[i].data
            _tx  = p_tx[0]
            tx   = <object>_tx  # increfs gain
            Py_DECREF(tx)       # for ^^^ <object>
            Py_DECREF(tx)       # for incref at send prepare

    # return what was selected
    cdef _chanop op = casev[selected].op
    if op == _DEFAULT:
        return selected, None
    if op == _CHANSEND:
        return selected, None

    if not (op == _CHANRECV or op == _CHANRECV_):
        bug("pyselect: chanselect returned with bad op")
    commaok = (op == _CHANRECV_)
    # we received NULL or the object and 1 reference to it (see pychan.recv_ for details)
    cdef object rx = None
    if _rx != NULL:
        rx = <object>_rx    # increfs again
        Py_DECREF(rx)       # since <object> convertion did incref

    if commaok:
        return selected, (rx, rxok)
    else:
        return selected, rx


# ---- for py tests ----

from golang._pycompat import im_class
import six, time

# unbound pychan.{send,recv,recv_}
_pychan_send  = pychan.send
_pychan_recv  = pychan.recv
_pychan_recv_ = pychan.recv_
if six.PY2:
    # on py3 class.func gets the func; on py2 - unbound_method(func)
    _pychan_send  = _pychan_send.__func__
    _pychan_recv  = _pychan_recv.__func__
    _pychan_recv_ = _pychan_recv_.__func__

cdef extern from "golang.h" nogil:
    bint _tchanblocked(_chan *ch, bint recv, bint send)

# _waitBlocked waits till a receive or send channel operation blocks waiting on the channel.
#
# For example `waitBlocked(ch.send)` waits till sender blocks waiting on ch.
def _waitBlocked(chanop):
    if im_class(chanop) is not pychan:
        pypanic("wait blocked: %r is method of a non-chan: %r" % (chanop, im_class(chanop)))
    cdef pychan pych = chanop.__self__
    cdef bint recv = False
    cdef bint send = False
    if chanop.__func__ is _pychan_recv:
        recv = True
    elif chanop.__func__ is _pychan_send:
        send = True
    else:
        pypanic("wait blocked: unexpected chan method: %r" % (chanop,))

    cdef _chan *_ch = pych.ch._ch
    if _ch == NULL:
        pypanic("wait blocked: called on nil channel")

    t0 = time.time()
    while 1:
        if _tchanblocked(_ch, recv, send):
            return
        now = time.time()
        if now-t0 > 10: # waited > 10 seconds - likely deadlock
            pypanic("deadlock")
        time.sleep(0)   # yield to another thread / coroutine

# ----------------------------------------

"""
from libc.stdio cimport printf

cdef void test() nogil:
    cdef chan a, b
    cdef void *tx = NULL
    cdef void *rx = NULL
    cdef int _

    cdef selcase sel[3]
    sel[0].op   = chansend
    sel[0].data = tx
    sel[1].op   = chanrecv
    sel[1].data = rx
    sel[2].op   = default
    _ = chanselect(sel, 3)  # XXX 3 -> array_len(sel)

    if _ == 0:
        printf('tx\n')
    if _ == 1:
        printf('rx\n')
    if _ == 2:
        printf('defaut\n')


def xtest():
    with nogil:
        test()
"""
