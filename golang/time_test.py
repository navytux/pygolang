# -*- coding: utf-8 -*-
# Copyright (C) 2019  Nexedi SA and Contributors.
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

from __future__ import print_function, absolute_import

from golang import select, _PanicError
from golang import time
from pytest import raises

# all timer tests operate in dt units
dt = 10*time.millisecond

# test_timer verifies that Timer/Ticker fire as expected.
def test_timer():
    # start timers at x5, x7 and x11 intervals an verify that the timers fire
    # in expected sequence. The times when the timers fire do not overlap in
    # checked range because intervals are prime and chosen so that they start
    # overlapping only after 35 (=5·7).
    tv = [] # timer events
    Tstart = time.now()

    t23 = time.Timer(23*dt)
    t5  = time.Timer( 5*dt)

    def _():
        tv.append(7)
        t7f.reset(7*dt)
    t7f = time.Timer( 7*dt, f=_)

    tx11 = time.Ticker(11*dt)

    while 1:
        _, _rx = select(
            t23.c.recv,     # 0
            t5 .c.recv,     # 1
            t7f.c.recv,     # 2
            tx11.c.recv,    # 3
        )
        if _ == 0:
            tv.append(23)
            break
        if _ == 1:
            tv.append(5)
            t5.reset(5*dt)
        if _ == 2:
            assert False, "t7f sent to channel; must only call func"
        if _ == 3:
            tv.append(11)

    Tend = time.now()
    assert (Tend - Tstart) >= 23*dt
    assert tv == [        5,  7,     5, 11,       7, 5,             5, 7,11,23]
    #             1 2 3 4 5 6 7 8 9 10  11 12 13 14 15 16 17 18 19 20 21 22 23


# test_timer_misc, similarly to test_timer, verifies misc timer convenience functions.
def test_timer_misc():
    tv = []
    Tstart = time.now()

    c23 = time.after(23*dt)
    c5  = time.after( 5*dt)

    def _():
        tv.append(7)
        t7f.reset(7*dt)
    t7f = time.after_func(7*dt, _)

    cx11 = time.tick(11*dt)

    while 1:
        _, _rx = select(
            c23.recv,       # 0
            c5 .recv,       # 1
            t7f.c.recv,     # 2
            cx11.recv,      # 3
        )
        if _ == 0:
            tv.append(23)
            break
        if _ == 1:
            tv.append(5)
            # NOTE 5 does not rearm in this test because there is no way to
            # rearm timer create by time.after().
        if _ == 2:
            assert False, "t7f sent to channel; must only call func"
        if _ == 3:
            tv.append(11)

    Tend = time.now()
    assert (Tend - Tstart) >= 23*dt
    assert tv == [        5,  7,        11,       7,                   7,11,23]
    #             1 2 3 4 5 6 7 8 9 10  11 12 13 14 15 16 17 18 19 20 21 22 23


# test_timer_stop verifies that .stop() cancels Timer or Ticker.
def test_timer_stop():
    tv = []

    t10 = time.Timer (10*dt)
    t2  = time.Timer ( 2*dt)    # will fire and cancel t3, tx5
    t3  = time.Timer ( 3*dt)    # will be canceled
    tx5 = time.Ticker( 5*dt)    # will be canceled

    while 1:
        _, _rx = select(
            t10.c.recv,     # 0
            t2 .c.recv,     # 1
            t3 .c.recv,     # 2
            tx5.c.recv,     # 3
        )
        if _ == 0:
            tv.append(10)
            break
        if _ == 1:
            tv.append(2)
            t3.stop()
            tx5.stop()
        if _ == 2:
            tv.append(3)
        if _ == 3:
            tv.append(5)

    assert tv == [  2,              10]
    #             1 2 3 4 5 6 7 8 9 10


# test_timer_stop_drain verifies that Timer/Ticker .stop() drains timer channel.
def test_timer_stop_drain():
    t  = time.Timer (1*dt)
    tx = time.Ticker(1*dt)

    time.sleep(2*dt)
    assert len(t.c)  == 1
    assert len(tx.c) == 1

    assert t.stop() == False
    assert len(t.c) == 0

    tx.stop()
    assert len(tx.c) == 0


# test_timer_reset_armed verifies that .reset() panics if called on armed timer.
def test_timer_reset_armed():
    # reset while armed
    t = time.Timer(10*dt)
    with raises(_PanicError):
        t.reset(5*dt)
