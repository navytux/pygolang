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

from golang import select, default, nilchan
from golang import context

# ready returns whether channel ch is ready.
def ready(ch):
    _, _rx = select(
            ch.recv,    # 0
            default,    # 1
    )

    if _ == 0:
        return True
    if _ == 1:
        return False

def test_context():
    bg = context.background()
    assert bg.err()     is None
    assert bg.done()    is nilchan

    # assertCtx asserts on state of _Context
    def assertCtx(ctx, children, err=None, done=False):
        assert isinstance(ctx, context._Context)
        assert ctx.err() is err
        assert ready(ctx.done()) == done
        assert ctx._children == children

    Z = set()   # empty set
    C = context.canceled
    Y = True

    ctx1, cancel1 = context.with_cancel(bg)
    assert ctx1._parentv == (bg,)
    assertCtx(ctx1,   Z)

    ctx11, cancel11 = context.with_cancel(ctx1)
    assert ctx11._parentv == (ctx1,)
    assertCtx(ctx1,   {ctx11})
    assertCtx(ctx11,  Z)

    ctx12, cancel12 = context.with_cancel(ctx1)
    assert ctx12._parentv == (ctx1,)
    assertCtx(ctx1,   {ctx11, ctx12})
    assertCtx(ctx11,  Z)
    assertCtx(ctx12,  Z)

    ctx121, cancel121 = context.with_cancel(ctx12)
    assert ctx121._parentv == (ctx12,)
    assertCtx(ctx1,   {ctx11, ctx12})
    assertCtx(ctx11,  Z)
    assertCtx(ctx12,  {ctx121})
    assertCtx(ctx121, Z)

    for _ in range(2):
        cancel11()
        assertCtx(ctx1,   {ctx12})
        assertCtx(ctx11,  Z, err=C, done=Y)
        assertCtx(ctx12,  {ctx121})
        assertCtx(ctx121, Z)

    for _ in range(2):
        cancel1()
        assertCtx(ctx1,   Z, err=C, done=Y)
        assertCtx(ctx11,  Z, err=C, done=Y)
        assertCtx(ctx12,  Z, err=C, done=Y)
        assertCtx(ctx121, Z, err=C, done=Y)
