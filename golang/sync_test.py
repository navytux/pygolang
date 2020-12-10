# -*- coding: utf-8 -*-
# Copyright (C) 2019-2020  Nexedi SA and Contributors.
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

from golang import go, chan, select, default, func, defer
from golang import sync, context, time
from pytest import raises, mark
from _pytest._code import Traceback
from golang.golang_test import import_pyx_tests, panics
from golang.time_test import dt
from six.moves import range as xrange
import sys, six

import_pyx_tests("golang._sync_test")

def _test_mutex(mu, lock, unlock):
    # verify that g2 mu.lock() blocks until g1 does mu.unlock()
    getattr(mu, lock)()
    l = []
    done = chan()
    def _():
        getattr(mu, lock)()
        l.append('b')
        getattr(mu, unlock)()
        done.close()
    go(_)
    time.sleep(1*dt)
    l.append('a')
    getattr(mu, unlock)()
    done.recv()
    assert l == ['a', 'b']

    # the same via with
    with mu:
        l = []
        done = chan()
        def _():
            with mu:
                l.append('d')
            done.close()
        go(_)
        time.sleep(1*dt)
        l.append('c')
    done.recv()
    assert l == ['c', 'd']

def test_mutex():           _test_mutex(sync.Mutex(),   'lock',    'unlock')
def test_sema():            _test_mutex(sync.Sema(),    'acquire', 'release')
def test_rwmutex_basic():   _test_mutex(sync.RWMutex(), 'Lock',    'Unlock')

def test_rwmutex():
    mu = sync.RWMutex()

    # Unlock  without lock -> panic
    # RUnlock without lock -> panic
    with panics("sync: Unlock of unlocked RWMutex"):    mu.Unlock()
    with panics("sync: RUnlock of unlocked RWMutex"):   mu.RUnlock()

    # Lock vs Lock; was also tested in test_rwmutex_basic
    mu.Lock()
    l = []
    done = chan()
    def _():
        mu.Lock()
        l.append('b')
        mu.Unlock()
        done.close()
    go(_)
    time.sleep(1*dt)
    l.append('a')
    mu.Unlock()
    done.recv()
    assert l == ['a', 'b']

# verify Lock/Unlock vs RLock/RUnlock interaction.
# if unlock_via_downgrade=Y, Lock is released via UnlockToRLock + RUnlock.
@mark.parametrize('unlock_via_downgrade', [False, True])
def test_rwmutex_lock_vs_rlock(unlock_via_downgrade):
    mu = sync.RWMutex()

    # Lock vs RLock
    l  = []  # accessed as R R R ... R  W  R R R ... R
    Nr1 = 10 # Nreaders queued before W
    Nr2 = 15 # Nreaders queued after  W
    mu.RLock()
    locked = chan(Nr1 + 1*3 + Nr2) # main <- R|W: mu locked
    rcont  = chan()                # main -> R: continue
    def R(): # readers
        mu.RLock()
        locked.send(('R', len(l)))
        rcont.recv()
        mu.RUnlock()
    for i in range(Nr1):
        go(R)

    # make sure all Nr1 readers entered mu.RLock
    for i in range(Nr1):
        assert locked.recv() == ('R', 0)

    # spawn W
    def W(): # 1 writer
        mu.Lock()
        time.sleep(Nr2*dt)  # give R2 readers more chance to call mu.RLock and run first
        locked.send('W')
        l.append('a')
        if not unlock_via_downgrade:
            locked.send('_WUnlock')
            mu.Unlock()
        else:
            locked.send('_WUnlockToRLock')
            mu.UnlockToRLock()
            time.sleep(Nr2*dt)
            locked.send('_WRUnlock')
            mu.RUnlock()
    go(W)

    # spawn more readers to verify that Lock has priority over RLock
    time.sleep(1*dt)    # give W more chance to call mu.Lock first
    for i in range(Nr2):
        go(R)

    # release main rlock, make sure nor W nor more R are yet ready, and let all readers continue
    time.sleep((1+1)*dt)
    mu.RUnlock()
    time.sleep(1*dt)
    for i in range(100):
        _, _rx = select(
            default,        # 0
            locked.recv,    # 1
        )
        assert _ == 0
    rcont.close()

    # W must get the lock first and all R2 readers only after it
    assert locked.recv() == 'W'
    if not unlock_via_downgrade:
        assert locked.recv() == '_WUnlock'
    else:
        assert locked.recv() == '_WUnlockToRLock'
    for i in range(Nr2):
        assert locked.recv() == ('R', 1)
    if unlock_via_downgrade:
        assert locked.recv() == '_WRUnlock'


# verify that sema.acquire can be woken up by sema.release not from the same
# thread which did the original sema.acquire.
def test_sema_wakeup_different_thread():
    sema = sync.Sema()
    sema.acquire()
    l = []
    done = chan()
    def _():
        time.sleep(1*dt)
        l.append('a')
        sema.release()
        done.close()
    go(_)
    sema.acquire()
    l.append('b')
    done.recv()
    assert l == ['a', 'b']


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

    with panics("sync: negative WaitGroup counter"):
        wg.done()


# PyErr_Restore_traceback_ok indicates whether python exceptions are restored with correct traceback.
# It is always the case for CPython, but PyPy < 7.3 had a bug:
# https://foss.heptapod.net/pypy/pypy/-/issues/3120
PyErr_Restore_traceback_ok = True
if 'PyPy' in sys.version and sys.pypy_version_info < (7,3):
    PyErr_Restore_traceback_ok = False

# WorkGroup must catch/propagate all exception classes.
# Python2 allows to raise old-style classes not derived from BaseException.
# Python3 allows to raise only BaseException derivatives.
if six.PY2:
    class MyError:
        def __init__(self, *args):
            self.args = args
else:
    class MyError(BaseException):
        pass

def test_workgroup():
    ctx, cancel = context.with_cancel(context.background())
    mu = sync.Mutex()

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
                    raise MyError('aaa')
        def f(ctx, i):
            Iam_f = 0
            _(ctx, i)

        wg.go(f, i)
    with raises(MyError) as exc:
        wg.wait()
    assert exc.type       is MyError
    assert exc.value.args == ('aaa',)
    if PyErr_Restore_traceback_ok:
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
                    raise MyError('bbb')
            if i == 1:
                ctx.done().recv()
                raise ValueError('ccc') # != MyError
        def f(ctx, i):
            Iam_f = 0
            _(ctx, i)

        wg.go(f, i)
    with raises(MyError) as exc:
        wg.wait()
    assert exc.type       is MyError
    assert exc.value.args == ('bbb',)
    if PyErr_Restore_traceback_ok:
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

@func
def test_workgroup_with():
    # verify with support for sync.WorkGroup
    ctx, cancel = context.with_cancel(context.background())
    defer(cancel)
    mu = sync.Mutex()

    # t1=ok, t2=ok
    l = [0, 0]
    with sync.WorkGroup(ctx) as wg:
        for i in range(2):
            def _(ctx, i):
                with mu:
                    l[i] = i+1
            wg.go(_, i)
    assert l == [1, 2]

    # t1=fail, t2=wait cancel, fail
    with raises(MyError) as exci:
        with sync.WorkGroup(ctx) as wg:
            def _(ctx):
                Iam_t1 = 0
                raise MyError('hello (fail)')
            wg.go(_)

            def _(ctx):
                ctx.done().recv()
                raise MyError('world (after zzz)')
            wg.go(_)

    e = exci.value
    assert e.__class__      is MyError
    assert e.args           == ('hello (fail)',)
    assert e.__cause__      is None
    assert e.__context__    is None
    assert e.__suppress_context__ == False
    if PyErr_Restore_traceback_ok:
        assert 'Iam_t1' in exci.traceback[-1].locals

    # t=ok, but code from under with raises
    l = [0]
    with raises(MyError) as exci:
        with sync.WorkGroup(ctx) as wg:
            def _(ctx):
                l[0] = 1
            wg.go(_)
            def bad():
                raise MyError('wow')
            bad()

    e = exci.value
    assert e.__class__      is MyError
    assert e.args           == ('wow',)
    assert e.__cause__      is None
    assert e.__context__    is None
    assert e.__suppress_context__ == False
    assert exci.traceback[-1].name == 'bad'
    assert l[0] == 1

    # t=fail, code from under with also raises
    with raises(MyError) as exci:
        with sync.WorkGroup(ctx) as wg:
            def f(ctx):
                raise MyError('fail from go')
            wg.go(f)
            def g():
                raise MyError('just raise')
            g()

    e = exci.value
    assert e.__class__      is MyError
    assert e.args           == ('fail from go',)
    assert e.__cause__      is None
    assert e.__context__    is not None
    assert e.__suppress_context__ == False
    assert exci.traceback[-1].name == 'f'
    e2 = e.__context__
    assert e2.__class__     is MyError
    assert e2.args          == ('just raise',)
    assert e2.__cause__     is None
    assert e2.__context__   is None
    assert e2.__suppress_context__ == False
    assert e2.__traceback__ is not None
    t2 = Traceback(e2.__traceback__)
    assert t2[-1].name == 'g'


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
            # NOTE not using `with raises` since it affects benchmark timing
            assert False, "did not raise"
