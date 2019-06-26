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

from golang import go, chan, _PanicError
from golang import sync, context
import time, threading
from pytest import raises
from six.moves import range as xrange

def test_once():
    once = sync.Once()
    l = []
    def _():
        l.append(1)

    once.do(_)
    assert l == [1]
    once.do(_)
    assert l == [1]
    once.do(_)
    assert l == [1]

    once = sync.Once()
    l = []
    def _():
        l.append(2)
        raise RuntimeError()

    with raises(RuntimeError):
        once.do(_)
    assert l == [2]
    once.do(_)  # no longer raises
    assert l == [2]
    once.do(_)  # no longer raises
    assert l == [2]


def test_waitgroup():
    wg = sync.WaitGroup()
    wg.add(2)

    ch = chan(3)
    def _():
        wg.wait()
        ch.send('a')
    for i in range(3):
        go(_)

    wg.done()
    assert len(ch) == 0
    time.sleep(0.1)
    assert len(ch) == 0
    wg.done()

    for i in range(3):
        assert ch.recv() == 'a'

    wg.add(1)
    go(_)
    time.sleep(0.1)
    assert len(ch) == 0
    wg.done()
    assert ch.recv() == 'a'

    with raises(_PanicError):
        wg.done()


def test_workgroup():
    ctx, cancel = context.with_cancel(context.background())
    mu = threading.Lock()

    # t1=ok, t2=ok
    wg = sync.WorkGroup(ctx)
    l = [0, 0]
    for i in range(2):
        def _(ctx, i):
            with mu:
                l[i] = i+1
        wg.go(_, i)
    wg.wait()
    assert l == [1, 2]

    # t1=fail, t2=ok, does not look at ctx
    wg = sync.WorkGroup(ctx)
    l = [0, 0]
    for i in range(2):
        def _(ctx, i):
            Iam__ = 0
            with mu:
                l[i] = i+1
                if i == 0:
                    raise RuntimeError('aaa')
        def f(ctx, i):
            Iam_f = 0
            _(ctx, i)

        wg.go(f, i)
    with raises(RuntimeError) as exc:
        wg.wait()
    assert exc.type       is RuntimeError
    assert exc.value.args == ('aaa',)
    assert 'Iam__' in exc.traceback[-1].locals
    assert 'Iam_f' in exc.traceback[-2].locals
    assert l == [1, 2]

    # t1=fail, t2=wait cancel, fail
    wg = sync.WorkGroup(ctx)
    l = [0, 0]
    for i in range(2):
        def _(ctx, i):
            Iam__ = 0
            with mu:
                l[i] = i+1
                if i == 0:
                    raise RuntimeError('bbb')
                if i == 1:
                    ctx.done().recv()
                    raise ValueError('ccc') # != RuntimeError
        def f(ctx, i):
            Iam_f = 0
            _(ctx, i)

        wg.go(f, i)
    with raises(RuntimeError) as exc:
        wg.wait()
    assert exc.type       is RuntimeError
    assert exc.value.args == ('bbb',)
    assert 'Iam__' in exc.traceback[-1].locals
    assert 'Iam_f' in exc.traceback[-2].locals
    assert l == [1, 2]


    # t1=ok,wait cancel  t2=ok,wait cancel
    # cancel parent
    wg = sync.WorkGroup(ctx)
    l = [0, 0]
    for i in range(2):
        def _(ctx, i):
            with mu:
                l[i] = i+1
                ctx.done().recv()
        wg.go(_, i)
    cancel()    # parent cancel - must be propagated into workgroup
    wg.wait()
    assert l == [1, 2]


# create/wait workgroup with 1 empty worker.
def bench_workgroup_empty(b):
    bg = context.background()
    def _(ctx):
        return

    for i in xrange(b.N):
        wg = sync.WorkGroup(bg)
        wg.go(_)
        wg.wait()

# create/wait workgroup with 1 worker that raises.
def bench_workgroup_raise(b):
    bg = context.background()
    def _(ctx):
        raise RuntimeError('aaa')

    for i in xrange(b.N):
        wg = sync.WorkGroup(bg)
        wg.go(_)
        try:
            wg.wait()
        except RuntimeError:
            pass
        else:
            # NOTE not using `with raises` since it visibly adds more overhead
            assert False, "did not raise"


import sys

def QQQ():
    exc = RuntimeError('aaa')
    try:
        raise exc
    finally:
        exc = None

def zzz(f):
    try:
        f()
    except Exception as exc:
        exc.__traceback__ = sys.exc_info()[2]


def bench_xxx(b):
    for i in xrange(b.N):
        zzz(QQQ)
