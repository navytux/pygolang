# -*- coding: utf-8 -*-
# cython: language_level=2
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

# ---- channels ----

# XXX nogil globally?

cdef void panic(const char *arg) nogil:
    1/0     # XXX -> throw?

cdef struct _WaitGroup

# chan is a channel with Go semantic.
cdef struct chan:
    unsigned    _cap        # channel capacity (elements)
    unsigned    _itemsize   # size of element

    # ._mu          lock                                    XXX -> _OSMutex (that can synchronize in between Procs) ?
    # ._dataq       deque *: data buffer                    XXX -> [_cap*_itemsize]
    # ._recvq       deque _RecvWaiting: blocked receivers   XXX -> list
    # ._sendq       deque _SendWaiting: blocked senders     XXX -> list
    bint        _closed

# _RecvWaiting represents a receiver waiting on a chan.
# XXX merge in _SendWaiting
cdef struct _RecvWaiting:
    _WaitGroup  *group  # group of waiters this receiver is part of
    chan        *chan   # channel receiver is waiting on

    # on wakeup: sender|closer -> receiver:
    void        *rx
    bint         ok

# _SendWaiting represents a sender waiting on a chan.
cdef struct _SendWaiting:
    _WaitGroup  *group  # group of waiters this sender is part of
    chan        *chan   # channel sender is waiting on

    void        *data   # data that was passed to send      XXX was `obj`

    # on wakeup: receiver|closer -> sender:
    bint        ok      # whether send succeeded (it will not on close)

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
    _SendWaiting    *which


# chaninit initializes chan<itemsize>(size).
cdef void chaninit(chan *ch, unsigned size, unsigned itemsize) nogil:
    ch._cap      = size
    ch._itemsize = itemsize
    ch._closed   = False

    # XXX alloc _dataq
    # XXX ._recvq = NULL
    # XXX ._sendq = NULL

# chansend sends data to a receiver.
#
# sizeof(*tx) must be ch._itemsize | tx=NULL.
cdef void chansend(chan *ch, void *tx) nogil:
    if ch is NULL:
        _blockforever()

    cdef _WaitGroup     g
    cdef _SendWaiting   me

    #ch._mu.acquire()
    if 1:
        ok = _trysend(ch, tx)
        if ok:
            return

        g.which     = NULL
        me.group    = &g
        me.chan     = ch
        me.data     = tx
        me.ok       = False
        #g._waitv.append(me)
        #ch._sendq.append(me)

    #ch._mu.release()

    waitgroup(&g)
    if not (g.which is &me):
        panic("bug")    # XXX
    if not me.ok:
        panic("send on closed channel")


# chanrecv_ is "comma-ok" version of chanrecv.
#
# ok is true - if receive was delivered by a successful send.
# ok is false - if receive is due to channel being closed and empty.
cdef bint chanrecv_(chan *ch, void *rx) nogil: # -> ok
    1/0 # TODO

# chanrecv receives from the channel.
cdef void chanrecv(chan *ch, void *rx) nogil:
    _ = chanrecv_(ch, rx)
    return

# _trysend(ch, obj) -> ok
#
# must be called with ._mu held.
# if ok or panic - returns with ._mu released.
# if !ok - returns with ._mu still being held.
cdef bint _trysend(chan *ch, void *tx) nogil:
    return False

IF 0:   # _trysend
    if ch._closed:
        ch._mu.release()
        panic("send on closed channel")

    # synchronous channel
    if ch._cap == 0:
        recv = _dequeWaiter(ch._recvq)
        if recv is None:
            return False

        ch._mu.release()
        recv.wakeup(obj, True)
        return True

    # buffered channel
    else:
        if len(ch._dataq) >= ch._cap:
            return False

        ch._dataq.append(obj)
        recv = _dequeWaiter(ch._recvq)
        ch._mu.release()
        if recv is not None:
            rx = ch._dataq.popleft()
            recv.wakeup(rx, True)
        return True
####

# _tryrecv() -> rx_=(rx, ok), ok
#
# must be called with ._mu held.
# if ok or panic - returns with ._mu released.
# if !ok - returns with ._mu still being held.
cdef bint _tryrecv(chan *ch, void *rx): # -> ok
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

IF 0:   # chanclose
    recvv = []
    sendv = []

    with self._mu:
        if self._closed:
            panic("close of closed channel")
        self._closed = True

        # schedule: wake-up all readers
        while 1:
            recv = _dequeWaiter(self._recvq)
            if recv is None:
                break
            recvv.append(recv)

        # schedule: wake-up all writers (they will panic)
        while 1:
            send = _dequeWaiter(self._sendq)
            if send is None:
                break
            sendv.append(send)

    # perform scheduled wakeups outside of ._mu
    for recv in recvv:
        recv.wakeup(None, False)
    for send in sendv:
        send.wakeup(False)
####

# XXX chanlen   (=














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

# waitgroup waits for winning case of group to complete.
cdef void waitgroup(_WaitGroup *group) nogil:
    #group._sema.acquire()  XXX
    pass

IF 0:   # _WaitGroup
    # wakeup wakes up the group.
    #
    # prior to wakeup try_to_win must have been called.
    # in practice this means that waiters queued to chan.{_send|_recv}q must
    # be dequeued with _dequeWaiter.
    def wakeup(self):
        assert self.which is not None
        self._sema.release()

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

# selcase represents one select case.
cdef struct selcase:
    void (*op)(chan *, void *)  # chansend/chanrecv/default
    void *data                  # chansend: tx; chanrecv: rx
    bint ok                     # comma-ok for rx

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


# ----------------------------------------

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
