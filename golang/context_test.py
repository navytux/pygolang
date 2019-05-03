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

from golang import context, nilchan
from golang.context import _ready as ready

def test_context():
    bg = context.background()
    assert bg.err()     is None
    assert bg.done()    is nilchan
    assert not ready(bg.done())
    assert bg.value("hello") is None

    # assertCtx asserts on state of _BaseCtx*
    def assertCtx(ctx, children, err=None, done=False):
        assert isinstance(ctx, context._BaseCtx)
        assert ctx.err() is err
        assert ready(ctx.done()) == done
        assert ctx._children == children

    Z = set()   # empty set
    C = context.canceled
    D = context.deadlineExceeded
    Y = True

    ctx1, cancel1 = context.with_cancel(bg)
    assert ctx1.done() is not bg.done()
    assertCtx(ctx1,     Z)

    ctx11, cancel11 = context.with_cancel(ctx1)
    assert ctx11.done() is not ctx1.done()
    assertCtx(ctx1,     {ctx11})
    assertCtx(ctx11,    Z)

    ctx111  = context.with_value(ctx11,  "hello", "alpha")
    assert ctx111.done() is ctx11.done()
    assert ctx111.value("hello") == "alpha"
    assert ctx111.value("abc")   is None
    assertCtx(ctx1,     {ctx11})
    assertCtx(ctx11,    {ctx111})
    assertCtx(ctx111,   Z)

    ctx1111 = context.with_value(ctx111, "beta",  "gamma")
    assert ctx1111.done() is ctx11.done()
    assert ctx1111.value("hello") == "alpha"
    assert ctx1111.value("beta")  == "gamma"
    assert ctx1111.value("abc")   is None
    assertCtx(ctx1,     {ctx11})
    assertCtx(ctx11,    {ctx111})
    assertCtx(ctx111,   {ctx1111})
    assertCtx(ctx1111,  Z)

    ctx12 = context.with_value(ctx1, "hello", "world")
    assert ctx12.done() is ctx1.done()
    assert ctx12.value("hello") == "world"
    assert ctx12.value("abc")   is None
    assertCtx(ctx1,     {ctx11, ctx12})
    assertCtx(ctx11,    {ctx111})
    assertCtx(ctx111,   {ctx1111})
    assertCtx(ctx1111,  Z)
    assertCtx(ctx12,    Z)

    ctx121, cancel121 = context.with_cancel(ctx12)
    assert ctx121.done() is not ctx12.done()
    assert ctx121.value("hello") == "world"
    assert ctx121.value("abc")   is None
    assertCtx(ctx1,     {ctx11, ctx12})
    assertCtx(ctx11,    {ctx111})
    assertCtx(ctx111,   {ctx1111})
    assertCtx(ctx1111,  Z)
    assertCtx(ctx12,    {ctx121})
    assertCtx(ctx121,   Z)

    ctx1211 = context.with_value(ctx121, "мир", "май")
    assert ctx1211.done() is ctx121.done()
    assert ctx1211.value("hello") == "world"
    assert ctx1211.value("мир")   == "май"
    assert ctx1211.value("abc")   is None
    assertCtx(ctx1,     {ctx11, ctx12})
    assertCtx(ctx11,    {ctx111})
    assertCtx(ctx111,   {ctx1111})
    assertCtx(ctx1111,  Z)
    assertCtx(ctx12,    {ctx121})
    assertCtx(ctx121,   {ctx1211})
    assertCtx(ctx1211,  Z)

    ctxM, cancelM = context.merge(ctx1111, ctx1211)
    assert ctxM.done() is not ctx1111.done()
    assert ctxM.done() is not ctx1211.done()
    assert ctxM.value("hello")  == "alpha"
    assert ctxM.value("мир")    == "май"
    assert ctxM.value("beta")   == "gamma"
    assert ctxM.value("abc")    is None
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
