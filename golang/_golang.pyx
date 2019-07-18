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

cdef struct _WaitGroup
cdef struct chan

# _RecvWaiting represents a receiver waiting on a chan.
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

    void        *tx     # data that was passed to send      XXX was `obj`

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
    int XXX


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
####
