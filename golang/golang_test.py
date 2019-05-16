# -*- coding: utf-8 -*-
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

from __future__ import print_function, absolute_import

from golang import go, chan, select, default, nilchan, _PanicError, func, panic, defer, recover
from pytest import raises
from os.path import dirname
import os, sys, time, threading, inspect, subprocess

import golang
from golang import _chan_recv, _chan_send
from golang._pycompat import im_class

def test_go():
    # leaked goroutine behaviour check: done in separate process because we need
    # to test process termination exit there.

    # adjust $PYTHONPATH to point to pygolang. This makes sure that external
    # script will succeed on `import golang` when running in-tree.
    dir_golang = dirname(__file__)  #     .../pygolang/golang
    dir_top    = dir_golang + '/..' # ~>  .../pygolang
    pathv = [dir_top]
    env = os.environ.copy()
    envpath = env.get('PYTHONPATH')
    if envpath is not None:
        pathv.append(envpath)
    env['PYTHONPATH'] = ':'.join(pathv)

    subprocess.check_call([sys.executable, dir_golang + "/testprog/golang_test_goleaked.py"],
            env=env)


# waitBlocked waits till a receive or send channel operation blocks waiting on the channel.
#
# For example `waitBlocked(ch.send)` waits till sender blocks waiting on ch.
def waitBlocked(chanop):
    if im_class(chanop) is not chan:
        panic("wait blocked: %r is method of a non-chan: %r" % (chanop, im_class(chanop)))
    ch = chanop.__self__
    recv = send = False
    if chanop.__func__ is _chan_recv:
        recv = True
    elif chanop.__func__ is _chan_send:
        send = True
    else:
        panic("wait blocked: unexpected chan method: %r" % (chanop,))

    t0 = time.time()
    while 1:
        with ch._mu:
            if recv and len(ch._recvq) > 0:
                return
            if send and len(ch._sendq) > 0:
                return
        now = time.time()
        if now-t0 > 10: # waited > 10 seconds - likely deadlock
            panic("deadlock")
        time.sleep(0)   # yield to another thread / coroutine


def test_chan():
    # sync: pre-close vs send/recv
    ch = chan()
    ch.close()
    assert ch.recv()    == None
    assert ch.recv_()   == (None, False)
    assert ch.recv_()   == (None, False)
    with raises(_PanicError): ch.send(0)
    with raises(_PanicError): ch.close()

    # sync: send vs recv
    ch = chan()
    def _():
        ch.send(1)
        assert ch.recv() == 2
        ch.close()
    go(_)
    assert ch.recv() == 1
    ch.send(2)
    assert ch.recv_() == (None, False)
    assert ch.recv_() == (None, False)

    # sync: close vs send
    ch = chan()
    def _():
        waitBlocked(ch.send)
        ch.close()
    go(_)
    with raises(_PanicError): ch.send(0)

    # close vs recv
    ch = chan()
    def _():
        waitBlocked(ch.recv)
        ch.close()
    go(_)
    assert ch.recv_() == (None, False)

    # sync: close vs multiple recv
    ch = chan()
    done = chan()
    mu = threading.Lock()
    s  = set()
    def _():
        assert ch.recv_() == (None, False)
        with mu:
            x = len(s)
            s.add(x)
        done.send(x)
    for i in range(3):
        go(_)
    ch.close()
    for i in range(3):
        done.recv()
    assert s == {0,1,2}

    # buffered
    ch = chan(3)
    done = chan()
    for _ in range(2):
        for i in range(3):
            assert len(ch) == i
            ch.send(i)
            assert len(ch) == i+1
        for i in range(3):
            assert ch.recv_() == (i, True)

    assert len(ch) == 0
    for i in range(3):
        ch.send(i)
    assert len(ch) == 3
    def _():
        waitBlocked(ch.send)
        assert ch.recv_() == (0, True)
        done.send('a')
        for i in range(1,4):
            assert ch.recv_() == (i, True)
        assert ch.recv_() == (None, False)
        done.send('b')
    go(_)
    ch.send(3)  # will block without receiver
    assert done.recv() == 'a'
    ch.close()
    assert done.recv() == 'b'


def test_select():
    N = 1000 # times to do repeated select/chan or select/select interactions

    # non-blocking try send: not ok
    ch = chan()
    _, _rx = select(
            (ch.send, 0),
            default,
    )
    assert (_, _rx) == (1, None)

    # non-blocking try recv: not ok
    _, _rx = select(
            ch.recv,
            default,
    )
    assert (_, _rx) == (1, None)

    _, _rx = select(
            ch.recv_,
            default,
    )
    assert (_, _rx) == (1, None)

    # non-blocking try send: ok
    ch = chan()
    done = chan()
    def _():
        i = 0
        while 1:
            x = ch.recv()
            if x == 'stop':
                break
            assert x == i
            i += 1
        done.close()
    go(_)

    for i in range(N):
        waitBlocked(ch.recv)
        _, _rx = select(
                (ch.send, i),
                default,
        )
        assert (_, _rx) == (0, None)
    ch.send('stop')
    done.recv()

    # non-blocking try recv: ok
    ch = chan()
    done = chan()
    def _():
        for i in range(N):
            ch.send(i)
        done.close()
    go(_)

    for i in range(N):
        waitBlocked(ch.send)
        if i % 2:
            _, _rx = select(
                    ch.recv,
                    default,
            )
            assert (_, _rx) == (0, i)
        else:
            _, _rx = select(
                    ch.recv_,
                    default,
            )
            assert (_, _rx) == (0, (i, True))
    done.recv()


    # blocking 2·send
    ch1 = chan()
    ch2 = chan()
    done = chan()
    def _():
        waitBlocked(ch1.send)
        assert ch1.recv() == 'a'
        done.close()
    go(_)

    _, _rx = select(
        (ch1.send, 'a'),
        (ch2.send, 'b'),
    )
    assert (_, _rx) == (0, None)
    done.recv()
    assert len(ch1._sendq) == len(ch1._recvq) == 0
    assert len(ch2._sendq) == len(ch2._recvq) == 0


    # blocking 2·recv
    ch1 = chan()
    ch2 = chan()
    done = chan()
    def _():
        waitBlocked(ch1.recv)
        ch1.send('a')
        done.close()
    go(_)

    _, _rx = select(
        ch1.recv,
        ch2.recv,
    )
    assert (_, _rx) == (0, 'a')
    done.recv()
    assert len(ch1._sendq) == len(ch1._recvq) == 0
    assert len(ch2._sendq) == len(ch2._recvq) == 0


    # blocking send/recv
    ch1 = chan()
    ch2 = chan()
    done = chan()
    def _():
        waitBlocked(ch1.send)
        assert ch1.recv() == 'a'
        done.close()
    go(_)

    _, _rx = select(
        (ch1.send, 'a'),
        ch2.recv,
    )
    assert (_, _rx) == (0, None)
    done.recv()
    assert len(ch1._sendq) == len(ch1._recvq) == 0
    assert len(ch2._sendq) == len(ch2._recvq) == 0


    # blocking recv/send
    ch1 = chan()
    ch2 = chan()
    done = chan()
    def _():
        waitBlocked(ch1.recv)
        ch1.send('a')
        done.close()
    go(_)

    _, _rx = select(
        ch1.recv,
        (ch2.send, 'b'),
    )
    assert (_, _rx) == (0, 'a')
    done.recv()
    assert len(ch1._sendq) == len(ch1._recvq) == 0
    assert len(ch2._sendq) == len(ch2._recvq) == 0


    # blocking send + nil channel
    z = nilchan
    for i in range(N):
        ch = chan()
        done = chan()
        def _():
            waitBlocked(ch.send)
            assert len(z._sendq) == len(z._recvq) == 0
            assert ch.recv() == 'c'
            done.close()
        go(_)

        _, _rx = select(
                z.recv,
                (z.send, 0),
                (ch.send, 'c'),
        )

        assert (_, _rx) == (2, None)
        done.recv()
        assert len(ch._sendq) == len(ch._recvq) == 0

    # blocking recv + nil channel
    for i in range(N):
        ch = chan()
        done = chan()
        def _():
            waitBlocked(ch.recv)
            assert len(z._sendq) == len(z._recvq) == 0
            ch.send('d')
            done.close()
        go(_)

        _, _rx = select(
                z.recv,
                (z.send, 0),
                ch.recv,
        )

        assert (_, _rx) == (2, 'd')
        done.recv()
        assert len(ch._sendq) == len(ch._recvq) == 0


    # buffered ping-pong
    ch = chan(1)
    for i in range(N):
        _, _rx = select(
            (ch.send, i),
            ch.recv,
        )
        assert _    == (i % 2)
        assert _rx  == (i - 1 if i % 2 else None)


    # select vs select
    # channels are recreated on every iteration.
    for i in range(N):
        ch1 = chan()
        ch2 = chan()
        done = chan()
        def _():
            _, _rx = select(
                (ch1.send, 'a'),
                (ch2.send, 'xxx2'),
            )
            assert (_, _rx) == (0, None)

            _, _rx = select(
                (ch1.send, 'yyy2'),
                ch2.recv,
            )
            assert (_, _rx) == (1, 'b')

            done.close()

        go(_)

        _, _rx = select(
            ch1.recv,
            (ch2.send, 'xxx1'),
        )
        assert (_, _rx) == (0, 'a')

        _, _rx = select(
            (ch1.send, 'yyy1'),
            (ch2.send, 'b'),
        )
        assert (_, _rx) == (1, None)

        done.recv()
        assert len(ch1._sendq) == len(ch1._recvq) == 0
        assert len(ch2._sendq) == len(ch2._recvq) == 0


    # select vs select
    # channels are shared for all iterations.
    # (this tries to trigger parasitic effects from already performed select)
    ch1 = chan()
    ch2 = chan()
    done = chan()
    def _():
        for i in range(N):
            _, _rx = select(
                (ch1.send, 'a%d' % i),
                (ch2.send, 'xxx2'),
            )
            assert (_, _rx) == (0, None)

            _, _rx = select(
                (ch1.send, 'yyy2'),
                ch2.recv,
            )
            assert (_, _rx) == (1, 'b%d' % i)

        done.close()

    go(_)

    for i in range(N):
        _, _rx = select(
            ch1.recv,
            (ch2.send, 'xxx1'),
        )
        assert (_, _rx) == (0, 'a%d' % i)

        _, _rx = select(
            (ch1.send, 'yyy1'),
            (ch2.send, 'b%d' % i),
        )
        assert (_, _rx) == (1, None)

    done.recv()
    assert len(ch1._sendq) == len(ch1._recvq) == 0
    assert len(ch2._sendq) == len(ch2._recvq) == 0


# BlocksForever is used in "blocks forever" tests where golang._blockforever
# is patched to raise instead of block.
class BlocksForever(Exception):
    pass

def test_blockforever():
    B = golang._blockforever
    def _(): raise BlocksForever()
    golang._blockforever = _
    try:
        _test_blockforever()
    finally:
        golang._blockforever = B

def _test_blockforever():
    z = nilchan
    with raises(BlocksForever): z.send(0)
    with raises(BlocksForever): z.recv()
    with raises(_PanicError):   z.close()   # to fully cover nilchan ops

    # select{} & nil-channel only
    with raises(BlocksForever): select()
    with raises(BlocksForever): select((z.send, 0))
    with raises(BlocksForever): select(z.recv)
    with raises(BlocksForever): select((z.send, 1), z.recv)


def test_method():
    # test how @func(cls) works
    # this also implicitly tests just @func, since @func(cls) uses that.

    class MyClass:
        def __init__(self, v):
            self.v = v

    @func(MyClass)
    def zzz(self, v, x=2, **kkkkwww):
        assert self.v == v
        return v + 1

    @func(MyClass)
    @staticmethod
    def mstatic(v):
        assert v == 5
        return v + 1

    @func(MyClass)
    @classmethod
    def mcls(cls, v):
        assert cls is MyClass
        assert v == 7
        return v + 1

    obj = MyClass(4)
    assert obj.zzz(4)       == 4 + 1
    assert obj.mstatic(5)   == 5 + 1
    assert obj.mcls(7)      == 7 + 1

    # this tests that @func (used by @func(cls)) preserves decorated function signature
    assert inspect.formatargspec(*inspect.getargspec(MyClass.zzz)) == '(self, v, x=2, **kkkkwww)'

    assert MyClass.zzz.__module__       == __name__
    assert MyClass.zzz.__name__         == 'zzz'

    assert MyClass.mstatic.__module__   == __name__
    assert MyClass.mstatic.__name__     == 'mstatic'

    assert MyClass.mcls.__module__      == __name__
    assert MyClass.mcls.__name__        == 'mcls'



def test_deferrecover():
    # regular defer calls
    v = []
    @func
    def _():
        defer(lambda: v.append(1))
        defer(lambda: v.append(2))
        defer(lambda: v.append(3))

    _()
    assert v == [3, 2, 1]

    # defers called even if exception is raised
    v = []
    @func
    def _():
        defer(lambda: v.append(1))
        defer(lambda: v.append(2))
        def _(): v.append('ran ok')
        defer(_)
        1/0

    with raises(ZeroDivisionError): _()
    assert v == ['ran ok', 2, 1]

    # defer without @func is caught and properly reported
    v = []
    def nofunc():
        defer(lambda: v.append('xx'))

    with raises(_PanicError) as exc:
        nofunc()
    assert exc.value.args == ("function nofunc uses defer, but not @func",)


    # panic in deferred call - all defers are called
    v = []
    @func
    def _():
        defer(lambda: v.append(1))
        defer(lambda: v.append(2))
        defer(lambda: panic(3))
        defer(lambda: v.append(4))

    with raises(_PanicError): _()
    assert v == [4, 2, 1]


    # defer + recover
    v = []
    @func
    def _():
        defer(lambda: v.append(1))
        def _():
            r = recover()
            assert r == "aaa"
            v.append('recovered ok')
        defer(_)
        defer(lambda: v.append(3))

        panic("aaa")

    _()
    assert v == [3, 'recovered ok', 1]


    # recover + panic in defer
    v = []
    @func
    def _():
        defer(lambda: v.append(1))
        defer(lambda: panic(2))
        def _():
            r = recover()
            assert r == "bbb"
            v.append('recovered 1')
        defer(_)
        defer(lambda: v.append(3))

        panic("bbb")

    with raises(_PanicError): _()
    assert v == [3, 'recovered 1', 1]


    # recover + panic in defer + recover
    v = []
    @func
    def _():
        defer(lambda: v.append(1))
        def _():
            r = recover()
            assert r == "ddd"
            v.append('recovered 2')
        defer(_)
        defer(lambda: panic("ddd"))
        def _():
            r = recover()
            assert r == "ccc"
            v.append('recovered 1')
        defer(_)
        defer(lambda: v.append(3))

        panic("ccc")

    _()
    assert v == [3, 'recovered 1', 'recovered 2', 1]


    # ---- recover() -> None ----

    # no exception / not under defer
    assert recover() is None

    # no exception/panic
    @func
    def _():
        def _():
            assert recover() is None
        defer(_)

    # not directly called by deferred func
    v = []
    @func
    def _():
        def f():
            assert recover() is None
            v.append('not recovered')
        defer(lambda: f())

        panic("zzz")

    with raises(_PanicError): _()
    assert v == ['not recovered']


    # ---- defer in @func(x) ----

    # defer in @func(cls)
    v = []

    class MyClass:
        pass

    @func(MyClass)
    def zzz(self):
        defer(lambda: v.append(1))
        defer(lambda: v.append(2))
        defer(lambda: v.append(3))

    obj = MyClass()
    obj.zzz()
    assert v == [3, 2, 1]


    # defer in std method
    v = []

    class MyClass:
        @func
        def method(self):
            defer(lambda: v.append(1))
            defer(lambda: v.append(2))
            defer(lambda: v.append(4))

    obj = MyClass()
    obj.method()
    assert v == [4, 2, 1]


    # defer in std @staticmethod
    v = []

    class MyClass:
        @func
        @staticmethod
        def mstatic():
            defer(lambda: v.append(1))
            defer(lambda: v.append(2))
            defer(lambda: v.append(5))

    MyClass.mstatic()
    assert v == [5, 2, 1]


    # defer in std @classmethod
    v = []

    class MyClass:
        @func
        @classmethod
        def mcls(cls):
            assert cls is MyClass
            defer(lambda: v.append(1))
            defer(lambda: v.append(2))
            defer(lambda: v.append(7))

    MyClass.mcls()
    assert v == [7, 2, 1]
