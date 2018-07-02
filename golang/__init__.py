# -*- coding: utf-8 -*-
# Copyright (C) 2018  Nexedi SA and Contributors.
#                     Kirill Smelkov <kirr@nexedi.com>
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
"""Package golang provides Go-like features for Python

- `go` spawns lightweight thread.
- `chan` and `select` provide channels with Go semantic.
- `method` allows to define methods separate from class.
- `gimport` allows to import python modules by full path in a Go workspace.

...
"""

__all__ = ['method', 'go', 'chan', 'select', 'default', 'panic', 'gimport']

from golang._gopath import gimport  # make gimport available from golang
import threading, collections, random

import six
from golang._pycompat import im_class

# TODO -> use gevent + fallback to !gevent implementation if gevent was not initialized.
# The following should automatically prefer to use gevent as golang backend:
#
#   from gevent import monkey; monkey.patch_all()
#   import golang ...
#
# But we should not use gevent by default - using it without its monkey patching
# does not make lots of sense and monkey patching has to be performed as the
# first step of a program (i.e. it is not good to put it under `import golang`).
#
# We can also provide `gpython` interpreter which does gevent monkey patching
# and puts everything from golang.__all__ to __builtins__.


# method decorator allows to define methods separate from class.
#
# For example:
#
#   @method(MyClass)
#   def my_method(self, ...):
#       ...
def method(cls):
    def deco(f):
        if isinstance(f, (staticmethod, classmethod)):
            func_name = f.__func__.func_name
        else:
            func_name = f.func_name
        setattr(cls, func_name, f)
    return deco


# panic stops normal execution of current goroutine.
def panic(arg):
    raise _PanicError(arg)

class _PanicError(Exception):
    pass

# go spawns lightweight thread.
#
# NOTE it spawns threading.Thread, but if gevent was activated via
# `gevent.monkey.patch_all`, it will spawn greenlet, not full OS thread.
def go(f, *argv, **kw):
    threading.Thread(target=f, args=argv, kwargs=kw).start()


# ---- channels ----

# _RecvWaiting represents a receiver waiting on a chan.
class _RecvWaiting(object):
    # .group    _WaitGroup      group of waiters this receiver is part of
    # .chan     chan            channel receiver is waiting on
    #
    # on wakeup: sender|closer -> receiver:
    #   .rx_                    rx_ for recv
    def __init__(self, group, ch):
        self.group = group
        self.chan  = ch
        group.register(self)

    # wakeup notifies waiting receiver that recv_ completed.
    def wakeup(self, rx, ok):
        self.rx_ = (rx, ok)
        self.group.wakeup()


# _SendWaiting represents a sender waiting on a chan.
class _SendWaiting(object):
    # .group    _WaitGroup      group of waiters this sender is part of
    # .chan     chan            channel sender is waiting on
    # .obj                      object that was passed to send
    #
    # on wakeup: receiver|closer -> sender:
    #   .ok     bool            whether send succeeded (it will not on close)
    def __init__(self, group, ch, obj):
        self.group = group
        self.chan  = ch
        self.obj   = obj
        group.register(self)

    # wakeup notifies waiting sender that send completed.
    def wakeup(self, ok):
        self.ok = ok
        self.group.wakeup()


# _WaitGroup is a group of waiting senders and receivers.
#
# Only 1 waiter from the group can succeed waiting.
class _WaitGroup(object):
    # ._waitv   [] of _{Send|Recv}Waiting
    # ._sema    semaphore   used for wakeup
    #
    # ._mu      lock
    #
    # on wakeup: sender|receiver -> group:
    #   .which  _{Send|Recv}Waiting     instance which succeeded waiting.
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
        with self._mu:  # NOTE order is always:  waiter.chan._mu > ._mu
            if self.which is not None:
                return False
            else:
                self.which = waiter
                return True

    # wait waits for winning case of group to complete.
    def wait(self):
        self._sema.acquire()

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


# _dequeWaiter dequeues a send or recv waiter from a channel's _recvq or _sendq.
#
# the channel owning {_recv|_send}q must be locked.
def _dequeWaiter(queue):
    while len(queue) > 0:
        w = queue.popleft()
        # if this waiter can win its group - return it.
        # if not - someone else from its group already has won, and so we anyway have
        # to remove the waiter from the queue.
        if w.group.try_to_win(w):
            return w

    return None


# chan is a channel with Go semantic.
class chan(object):
    # ._cap         channel capacity
    # ._mu          lock
    # ._dataq       deque *: data buffer
    # ._recvq       deque _RecvWaiting: blocked receivers
    # ._sendq       deque _SendWaiting: blocked senders
    # ._closed      bool

    def __init__(self, size=0):
        self._cap       = size
        self._mu        = threading.Lock()
        self._dataq     = collections.deque()
        self._recvq     = collections.deque()
        self._sendq     = collections.deque()
        self._closed    = False

    # send sends object to a receiver.
    #
    # .send(obj)
    def send(self, obj):
        self._mu.acquire()
        if 1:
            ok = self._trysend(obj)
            if ok:
                return

            g  = _WaitGroup()
            me = _SendWaiting(g, self, obj)
            self._sendq.append(me)

        self._mu.release()

        g.wait()
        assert g.which is me
        if not me.ok:
            panic("send on closed channel")

    # recv_ is "comma-ok" version of recv.
    #
    # ok is true - if receive was delivered by a successful send.
    # ok is false - if receive is due to channel being closed and empty.
    #
    # .recv_() -> (rx, ok)
    def recv_(self):
        self._mu.acquire()
        if 1:
            rx_, ok = self._tryrecv()
            if ok:
                return rx_

            g  = _WaitGroup()
            me = _RecvWaiting(g, self)
            self._recvq.append(me)

        self._mu.release()

        g.wait()
        assert g.which is me
        return me.rx_

    # recv receives from the channel.
    #
    # .recv() -> rx
    def recv(self):
        rx, _ = self.recv_()
        return rx

    # _trysend(obj) -> ok
    #
    # must be called with ._mu held.
    # if ok or panic - returns with ._mu released.
    # if !ok - returns with ._mu still being held.
    def _trysend(self, obj):
        if self._closed:
            self._mu.release()
            panic("send on closed channel")

        # synchronous channel
        if self._cap == 0:
            recv = _dequeWaiter(self._recvq)
            if recv is None:
                return False

            self._mu.release()
            recv.wakeup(obj, True)
            return True

        # buffered channel
        else:
            if len(self._dataq) >= self._cap:
                return False

            self._dataq.append(obj)
            recv = _dequeWaiter(self._recvq)
            self._mu.release()
            if recv is not None:
                rx = self._dataq.popleft()
                recv.wakeup(rx, True)
            return True

    # _tryrecv() -> rx_=(rx, ok), ok
    #
    # must be called with ._mu held.
    # if ok or panic - returns with ._mu released.
    # if !ok - returns with ._mu still being held.
    def _tryrecv(self):
        # buffered
        if len(self._dataq) > 0:
            rx = self._dataq.popleft()

            # wakeup a blocked writer, if there is any
            send = _dequeWaiter(self._sendq)
            self._mu.release()
            if send is not None:
                self._dataq.append(send.obj)
                send.wakeup(True)

            return (rx, True), True

        # closed
        if self._closed:
            self._mu.release()
            return (None, False), True

        # sync | empty: there is waiting writer
        send = _dequeWaiter(self._sendq)
        if send is None:
            return (None, False), False

        self._mu.release()
        rx = send.obj
        send.wakeup(True)
        return (rx, True), True


    # close closes sending side of the channel.
    def close(self):
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


    def __len__(self):
        return len(self._dataq)


# default represents default case for select.
default  = object()

# unbound chan.{send,recv,recv_}
_chan_send  = chan.send
_chan_recv  = chan.recv
_chan_recv_ = chan.recv_
if six.PY2:
    # on py3 class.func gets the func; on py2 - unbound_method(func)
    _chan_send  = _chan_send.__func__
    _chan_recv  = _chan_recv.__func__
    _chan_recv_ = _chan_recv_.__func__

# select executes one ready send or receive channel case.
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
def select(*casev):
    # XXX select on nil chan?
    # XXX select{} -> block forever

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

    # second pass: subscribe and wait on all rx/tx cases
    g = _WaitGroup()

    try:
        for n, ch, tx in sendv:
            ch._mu.acquire()
            if 1:
                ok = ch._trysend(tx)
                if ok:
                    return n, None

                w = _SendWaiting(g, ch, tx)
                w.sel_n = n
                ch._sendq.append(w)
            ch._mu.release()

        for n, ch, commaok in recvv:
            ch._mu.acquire()
            if 1:
                rx_, ok = ch._tryrecv()
                if ok:
                    if not commaok:
                        rx, ok = rx_
                        rx_ = rx
                    return n, rx_

                w = _RecvWaiting(g, ch)
                w.sel_n = n
                w.sel_commaok = commaok
                ch._recvq.append(w)
            ch._mu.release()

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

    finally:
        # unsubscribe not-succeeded waiters
        g.dequeAll()
