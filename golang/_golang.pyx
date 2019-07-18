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

IF 0:
    def __init__(self, group, ch):
        self.group = group
        self.chan  = ch
        group.register(self)

    # wakeup notifies waiting receiver that recv_ completed.
    cdef wakeup(self, rx, ok):
        self.rx_ = (rx, ok)
        self.group.wakeup()
####


# _SendWaiting represents a sender waiting on a chan.
cdef struct _SendWaiting:
    _WaitGroup  *group  # group of waiters this sender is part of
    chan        *chan   # channel sender is waiting on

    void        *tx     # data that was passed to send      XXX was `obj`

    # on wakeup: receiver|closer -> sender:
    bint        ok      # whether send succeeded (it will not on close)

IF 0:
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
