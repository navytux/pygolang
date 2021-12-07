# -*- coding: utf-8 -*-
# Copyright (C) 2019-2021  Nexedi SA and Contributors.
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

from golang import nilchan, select, default
from golang import context, _context, time
from golang._context import _tctxAssertChildren as tctxAssertChildren
from golang.time_test import dt

# assertCtx asserts on state of _BaseCtx*
def assertCtx(ctx, children, deadline=None, err=None, done=False):
    assert isinstance(ctx, _context.PyContext)
    assert ctx.deadline() == deadline
    assert ctx.err() == err
    ctxdone = ctx.done()
    assert ready(ctxdone) == done
    tctxAssertChildren(ctx, children)
    for i in range(10): # repeated .done() returns the same pyobject
        assert ctx.done() is ctxdone

Z = set()   # empty set
C = context.canceled
D = context.deadlineExceeded
Y = True

bg = context.background()

# keys for context values
class Key:
    def __init__(self, key):
        self._key = key
    def __repr__(self):
        return "Key(%r)" % (self._key,)

    # __hash__ and __eq__ so that Key(x) == Key(x) to verify that keys are
    # compared by identity, _not_ equality.
    def __hash__(self):
        return hash(self._key)
    def __eq__(lhs, rhs):
        if not isinstance(rhs, Key):
            return False
        return lhs._key == rhs._key
kA      = Key("a")
assert kA == kA
assert not (kA != kA)
assert kA == Key("a")
assert kA != Key("b")
kHello  = Key("hello")
kHello2 = Key("hello")
assert kHello is not kHello2
assert kHello    ==  kHello2
kAbc    = Key("abc")
kBeta   = Key("beta")
kMir    = Key("мир")


# test_context exercises with_cancel / with_value and merge.
# deadlines are tested in test_deadline.
def test_context():
    assert bg.err()         is None
    assert bg.done()        == nilchan
    assert bg.deadline()    is None
    assert not ready(bg.done())
    assert bg.value(kHello) is None

    ctx1, cancel1 = context.with_cancel(bg)
    assert ctx1.done() != bg.done()
    assertCtx(ctx1,     Z)

    ctx11, cancel11 = context.with_cancel(ctx1)
    assert ctx11.done() != ctx1.done()
    assertCtx(ctx1,     {ctx11})
    assertCtx(ctx11,    Z)

    vAlpha = Key("alpha")   # value object; Key is just reused as placeholder
    ctx111  = context.with_value(ctx11,  kHello, vAlpha)
    assert ctx111.done() == ctx11.done()
    assert ctx111.value(kHello)  is vAlpha  # original value object is returned
    assert ctx111.value(kHello2) is None    # _not_ vAlpha: keys are compared by identity
    assert ctx111.value(kAbc)    is None
    assertCtx(ctx1,     {ctx11})
    assertCtx(ctx11,    {ctx111})
    assertCtx(ctx111,   Z)

    ctx1111 = context.with_value(ctx111, kBeta,  "gamma")
    assert ctx1111.done() == ctx11.done()
    assert ctx1111.value(kHello) is vAlpha
    assert ctx1111.value(kBeta)  == "gamma"
    assert ctx1111.value(kAbc)   is None
    assertCtx(ctx1,     {ctx11})
    assertCtx(ctx11,    {ctx111})
    assertCtx(ctx111,   {ctx1111})
    assertCtx(ctx1111,  Z)


    ctx12 = context.with_value(ctx1, kHello, "world")
    assert ctx12.done() == ctx1.done()
    assert ctx12.value(kHello) == "world"
    assert ctx12.value(kAbc)   is None
    assertCtx(ctx1,     {ctx11, ctx12})
    assertCtx(ctx11,    {ctx111})
    assertCtx(ctx111,   {ctx1111})
    assertCtx(ctx1111,  Z)
    assertCtx(ctx12,    Z)

    ctx121, cancel121 = context.with_cancel(ctx12)
    assert ctx121.done() != ctx12.done()
    assert ctx121.value(kHello) == "world"
    assert ctx121.value(kAbc)   is None
    assertCtx(ctx1,     {ctx11, ctx12})
    assertCtx(ctx11,    {ctx111})
    assertCtx(ctx111,   {ctx1111})
    assertCtx(ctx1111,  Z)
    assertCtx(ctx12,    {ctx121})
    assertCtx(ctx121,   Z)

    ctx1211 = context.with_value(ctx121, kMir, "май")
    assert ctx1211.done() == ctx121.done()
    assert ctx1211.value(kHello) == "world"
    assert ctx1211.value(kMir)   == "май"
    assert ctx1211.value(kAbc)   is None
    assertCtx(ctx1,     {ctx11, ctx12})
    assertCtx(ctx11,    {ctx111})
    assertCtx(ctx111,   {ctx1111})
    assertCtx(ctx1111,  Z)
    assertCtx(ctx12,    {ctx121})
    assertCtx(ctx121,   {ctx1211})
    assertCtx(ctx1211,  Z)

    ctxM, cancelM = context.merge(ctx1111, ctx1211)
    assert ctxM.done() != ctx1111.done()
    assert ctxM.done() != ctx1211.done()
    assert ctxM.value(kHello)   is vAlpha
    assert ctxM.value(kMir)     == "май"
    assert ctxM.value(kBeta)    == "gamma"
    assert ctxM.value(kAbc)     is None
    assertCtx(ctx1,     {ctx11, ctx12})
    assertCtx(ctx11,    {ctx111})
    assertCtx(ctx111,   {ctx1111})
    assertCtx(ctx1111,  {ctxM})
    assertCtx(ctx12,    {ctx121})
    assertCtx(ctx121,   {ctx1211})
    assertCtx(ctx1211,  {ctxM})
    assertCtx(ctxM,     Z)


    for _ in range(2):
        cancel11()
        assertCtx(ctx1,     {ctx12})
        assertCtx(ctx11,    Z, err=C, done=Y)
        assertCtx(ctx111,   Z, err=C, done=Y)
        assertCtx(ctx1111,  Z, err=C, done=Y)
        assertCtx(ctx12,    {ctx121})
        assertCtx(ctx121,   {ctx1211})
        assertCtx(ctx1211,  Z)
        assertCtx(ctxM,     Z, err=C, done=Y)

    for _ in range(2):
        cancel1()
        assertCtx(ctx1,     Z, err=C, done=Y)
        assertCtx(ctx11,    Z, err=C, done=Y)
        assertCtx(ctx111,   Z, err=C, done=Y)
        assertCtx(ctx1111,  Z, err=C, done=Y)
        assertCtx(ctx12,    Z, err=C, done=Y)
        assertCtx(ctx121,   Z, err=C, done=Y)
        assertCtx(ctx1211,  Z, err=C, done=Y)
        assertCtx(ctxM,     Z, err=C, done=Y)


# test_deadline exercises deadline-related context functionality.
def test_deadline():
    t0 = time.now()
    d1 = t0 + 10*dt
    d2 = t0 + 20*dt
    d3 = t0 + 30*dt

    ctx1, cancel1 = context.with_deadline(bg, d2)
    assert ctx1.done() != bg.done()
    assertCtx(ctx1, Z, deadline=d2)

    ctx11 = context.with_value(ctx1, kA, "b")
    assert ctx11.done() == ctx1.done()
    assert ctx11.value(kA) == "b"
    assertCtx(ctx1,     {ctx11},        deadline=d2)
    assertCtx(ctx11,    Z,              deadline=d2)

    ctx111, cancel111 = context.with_cancel(ctx11)
    assert ctx111.done() != ctx11.done
    assertCtx(ctx1,     {ctx11},        deadline=d2)
    assertCtx(ctx11,    {ctx111},       deadline=d2)
    assertCtx(ctx111,   Z,              deadline=d2)

    ctx1111, cancel1111 = context.with_deadline(ctx111, d3) # NOTE deadline > parent
    assert ctx1111.done() != ctx111.done()
    assertCtx(ctx1,     {ctx11},        deadline=d2)
    assertCtx(ctx11,    {ctx111},       deadline=d2)
    assertCtx(ctx111,   {ctx1111},      deadline=d2)
    assertCtx(ctx1111,  Z,              deadline=d2)    # NOTE not d3

    ctx12, cancel12 = context.with_deadline(ctx1, d1)
    assert ctx12.done() != ctx1.done()
    assertCtx(ctx1,     {ctx11, ctx12}, deadline=d2)
    assertCtx(ctx11,    {ctx111},       deadline=d2)
    assertCtx(ctx111,   {ctx1111},      deadline=d2)
    assertCtx(ctx1111,  Z,              deadline=d2)
    assertCtx(ctx12,    Z,              deadline=d1)

    ctxM, cancelM = context.merge(ctx1111, ctx12)
    assert ctxM.done() != ctx1111.done()
    assert ctxM.done() != ctx12.done()
    assert ctxM.value(kA) == "b"
    assertCtx(ctx1,     {ctx11, ctx12}, deadline=d2)
    assertCtx(ctx11,    {ctx111},       deadline=d2)
    assertCtx(ctx111,   {ctx1111},      deadline=d2)
    assertCtx(ctx1111,  {ctxM},         deadline=d2)
    assertCtx(ctx12,    {ctxM},         deadline=d1)
    assertCtx(ctxM,     Z,              deadline=d1)

    time.sleep(11*dt)

    assertCtx(ctx1,     {ctx11},        deadline=d2)
    assertCtx(ctx11,    {ctx111},       deadline=d2)
    assertCtx(ctx111,   {ctx1111},      deadline=d2)
    assertCtx(ctx1111,  Z,              deadline=d2)
    assertCtx(ctx12,    Z,              deadline=d1, err=D, done=Y)
    assertCtx(ctxM,     Z,              deadline=d1, err=D, done=Y)

    # explicit cancel first -> err=canceled instead of deadlineExceeded
    for i in range(2):
        cancel1()
        assertCtx(ctx1,     Z,          deadline=d2, err=C, done=Y)
        assertCtx(ctx11,    Z,          deadline=d2, err=C, done=Y)
        assertCtx(ctx111,   Z,          deadline=d2, err=C, done=Y)
        assertCtx(ctx1111,  Z,          deadline=d2, err=C, done=Y)
        assertCtx(ctx12,    Z,          deadline=d1, err=D, done=Y)
        assertCtx(ctxM,     Z,          deadline=d1, err=D, done=Y)


    # with_timeout
    ctx, cancel = context.with_timeout(bg, 10*dt)
    assert ctx.done() != bg.done()
    d = ctx.deadline()
    assert abs(d - (time.now() + 10*dt)) < 1*dt
    assertCtx(ctx,  Z,  deadline=d)

    time.sleep(11*dt)
    assertCtx(ctx,  Z,  deadline=d, err=D, done=Y)


# test_already_canceled verifies context creation from already canceled parent.
# this used to deadlock.
def test_already_canceled():
    parent, pcancel = context.with_cancel(bg)
    assertCtx(parent, Z)
    pcancel()
    assertCtx(parent, Z, err=C, done=Y)

    ctxC, _ = context.with_cancel(parent)
    assert ctxC.done() != parent.done()
    assertCtx(parent, Z, err=C, done=Y)  # no ctxC in children
    assertCtx(ctxC,   Z, err=C, done=Y)

    ctxT, _ = context.with_timeout(parent, 10*dt)
    d = ctxT.deadline()
    assert ctxT.done() != parent.done()
    assertCtx(parent, Z, err=C, done=Y)  # no ctxT in children
    assertCtx(ctxT,   Z, deadline=d, err=C, done=Y)

    d = time.now() + 10*dt
    ctxD, _ = context.with_deadline(parent, d)
    assert ctxD.done() != parent.done()
    assertCtx(parent, Z, err=C, done=Y)  # no ctxD in children
    assertCtx(ctxD,   Z, deadline=d, err=C, done=Y)

    ctxM, _ = context.merge(parent, bg)
    assert ctxM.done() != parent.done()
    assertCtx(parent, Z, err=C, done=Y)  # no ctxM in children
    assertCtx(ctxM,   Z, err=C, done=Y)

    ctxV    = context.with_value(parent, kHello, "world")
    assert ctxV.done() == parent.done()
    assert ctxV.value(kHello) == "world"
    assertCtx(parent, Z, err=C, done=Y)  # no ctxV in children
    assertCtx(ctxV,   Z, err=C, done=Y)


# ---- misc ----

# _ready returns whether channel ch is ready.
def ready(ch):
    _, _rx = select(
            ch.recv,    # 0
            default,    # 1
    )
    if _ == 0:
        return True
    if _ == 1:
        return False
