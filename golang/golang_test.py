# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021  Nexedi SA and Contributors.
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

from golang import go, chan, select, default, nilchan, _PanicError, func, panic, \
        defer, recover, u, b
from golang.gcompat import qq
from golang import sync
from golang.strconv_test import byterange
from pytest import raises, mark, fail
from _pytest._code import Traceback
from os.path import dirname
import os, sys, inspect, importlib, traceback, doctest
from subprocess import Popen, PIPE
import six
from six import text_type as unicode
from six.moves import range as xrange
import gc, weakref, warnings
import re

from golang import _golang_test
from golang._golang_test import pywaitBlocked as waitBlocked, pylen_recvq as len_recvq, \
        pylen_sendq as len_sendq, pypanicWhenBlocked as panicWhenBlocked

# directories
dir_golang   = dirname(__file__)        # .../pygolang/golang
dir_pygolang = dirname(dir_golang)      # .../pygolang
dir_testprog = dir_golang + "/testprog" # .../pygolang/golang/testprog


# pyx/c/c++ tests/benchmarks -> {test,bench}_pyx_* in caller's globals.
def import_pyx_tests(modpath):
    mod = importlib.import_module(modpath)
    callf = inspect.currentframe().f_back   # caller's frame
    callg = callf.f_globals                 # caller's globals
    tbre  = re.compile("(test|bench)_(.+)")
    for f in dir(mod):
        m = tbre.match(f)
        if m is not None:
            kind, name = m.group(1), m.group(2)
            gf = kind + "_pyx_" + name # test_chan_nogil -> test_pyx_chan_nogil

            # define a python function with gf name (if we use f directly pytest
            # will say "cannot collect 'test_pyx_chan_nogil' because it is not a function")
            if kind == "test":
                def _(func=getattr(mod, f)):
                    func()
            elif kind == "bench":
                def _(b, func=getattr(mod, f)):
                    func(b)
            else:
                panic("unreachable")
            _.__name__ = gf
            callg[gf] = _

import_pyx_tests("golang._golang_test")


# leaked goroutine behaviour check: done in separate process because we need
# to test process termination exit there.
def test_go_leaked():
    pyrun([dir_testprog + "/golang_test_goleaked.py"])

# benchmark go+join a thread/coroutine.
# pyx/nogil mirror is in _golang_test.pyx
def bench_go(b):
    done = chan()
    def _():
        done.send(1)

    for i in xrange(b.N):
        go(_)
        done.recv()


def test_chan():
    # sync: pre-close vs send/recv
    ch = chan()
    ch.close()
    assert ch.recv()    == None
    assert ch.recv_()   == (None, False)
    assert ch.recv_()   == (None, False)
    with panics("send on closed channel"):  ch.send(0)
    with panics("close of closed channel"): ch.close()

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
    with panics("send on closed channel"):  ch.send(0)

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
    mu = sync.Mutex()
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

    # buffered: releases objects in buffer on chan gc
    ch = chan(3)
    class Obj(object): pass
    obj1 = Obj(); w1 = weakref.ref(obj1); assert w1() is obj1
    obj2 = Obj(); w2 = weakref.ref(obj2); assert w2() is obj2
    ch.send(obj1)
    ch.send(obj2)
    del obj1
    del obj2
    gc.collect()
    assert w1() is not None
    assert w2() is not None
    ch = None
    gc.collect()
    # pypy needs another GC run: pychan does Py_DECREF on buffered objects, but
    # on pypy cpyext objects are not deallocated from Py_DECREF even if
    # ob_refcnt goes to zero - the deallocation is delayed until GC run.
    # see also: http://doc.pypy.org/en/latest/discussion/rawrefcount.html
    gc.collect()
    assert w1() is None
    assert w2() is None

# test for buffered chan bug when ch._mu was released too early in _trysend.
def test_chan_buf_send_vs_tryrecv_race():
    # there was a bug when for buffered channel _trysend(ch) was releasing
    # ch._mu before further popping element from ch._dataq. If there was
    # another _tryrecv running concurrently to _trysend, that _tryrecv could
    # pop the element and _trysend would in turn try to pop on empty ch._dataq
    # leading to oops. The test tries to reproduce the following scenario:
    #
    #   T1(recv)          T2(send)                T3(_tryrecv)
    #
    # recv(blocked)
    #
    #                ch.mu.lock
    #                ch.dataq.append(x)
    #                ch.mu.unlock()
    #                                           ch.mu.lock
    #                                           ch.dataq.popleft()
    #
    #                # oopses since T3 already
    #                # popped the value
    #                ch.dataq.popleft()
    ch   = chan(1) # buffered
    done = chan()
    N = 1000

    # T1: recv(blocked)
    def _():
        for i in range(N):
            assert ch.recv() == i
        done.send(1)
    go(_)

    tryrecv_ctl = chan()  # send <-> _tryrecv sync

    # T2: send after recv is blocked -> _trysend succeeds
    def _():
        for i in range(N):
            waitBlocked(ch.recv)        # ch.recv() ^^^ entered ch._recvq
            tryrecv_ctl.send('start')   # signal _tryrecv to start
            ch.send(i)
            assert tryrecv_ctl.recv() == 'done'  # wait _tryrecv to finish
        done.send(1)
    go(_)

    # T3: _tryrecv running in parallel to _trysend
    def _():
        for i in range(N):
            assert tryrecv_ctl.recv() == 'start'
            _, _rx = select(
                    ch.recv,    # 0
                    default,    # 1
            )
            assert (_, _rx) == (1, None)
            tryrecv_ctl.send('done')
        done.send(1)
    go(_)

    for i in range(3):
        done.recv()

# test for buffered chan bug when ch._mu was released too early in _tryrecv.
def test_chan_buf_recv_vs_tryrecv_race():
    # (see test_chan_buf_send_vs_tryrecv_race for similar problem description)
    #
    #   T1(send)          T2(recv)                T3(_trysend)
    #
    # send(blocked)
    #
    #                ch.mu.lock
    #                ch.dataq.popleft()
    #                send = _dequeWaiter(ch._sendq)
    #                ch.mu.unlock()
    #
    #                                           ch.mu.lock
    #                                           len(ch.dataq) == 0 -> ok to append
    #
    #                                           # erroneously succeeds sending while
    #                                           # it must not
    #                                           ch.dataq.append(x)
    #
    #                ch.dataq.append(send.obj)
    ch   = chan(1) # buffered
    done = chan()
    N = 1000

    # T1: send(blocked)
    def _():
        for i in range(1 + N):
            ch.send(i)
        done.send(1)
    go(_)

    trysend_ctl = chan()  # recv <-> _trysend sync

    # T2: recv after send is blocked -> _tryrecv succeeds
    def _():
        for i in range(N):
            waitBlocked(ch.send)        # ch.send() ^^^ entered ch._sendq
            assert len(ch) == 1         # and 1 element was already buffered
            trysend_ctl.send('start')   # signal _trysend to start
            assert ch.recv() == i
            assert trysend_ctl.recv() == 'done' # wait _trysend to finish
        done.send(1)
    go(_)

    # T3: _trysend running in parallel to _tryrecv
    def _():
        for i in range(N):
            assert trysend_ctl.recv() == 'start'
            _, _rx = select(
                    (ch.send, 'i%d' % i),   # 0
                    default,                # 1
            )
            assert (_, _rx) == (1, None), ('i%d' % i)
            trysend_ctl.send('done')
        done.send(1)
    go(_)

    for i in range(3):
        done.recv()

# send/recv on the same channel in both directions.
# this triggers https://bugs.python.org/issue38106 on MacOS.
def test_chan_sendrecv_2way():
    N = 1000

    ch = chan()
    def _():
        for i in range(N):
            assert ch.recv() == ('hello %d' % i)
            ch.send('world %d' % i)
    go(_)

    for i in range(N):
        ch.send('hello %d' % i)
        assert ch.recv() == ('world %d' % i)


# benchmark sync chan send/recv.
# pyx/nogil mirror is in _golang_test.pyx
def bench_chan(b):
    ch   = chan()
    done = chan()
    def _():
        while 1:
            _, ok = ch.recv_()
            if not ok:
                done.close()
                return
    go(_)

    for i in xrange(b.N):
        ch.send(1)
    ch.close()
    done.recv()


def test_select():
    N = 1000 # times to do repeated select/chan or select/select interactions

    # sync: close vs select(send)
    ch = chan()
    def _():
        waitBlocked(ch.send)
        ch.close()
    go(_)
    with panics("send on closed channel"): select((ch.send, 0))

    # sync: close vs select(recv)
    ch = chan()
    def _():
        waitBlocked(ch.recv)
        ch.close()
    go(_)
    assert select(ch.recv) == (0, None)

    # non-blocking try send: not ok
    ch = chan()
    for i in range(N):
        _, _rx = select(
                (ch.send, 0),
                default,
        )
        assert (_, _rx) == (1, None)

    # non-blocking try recv: not ok
    for i in range(N):
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
        while 1:
            waitBlocked(ch1.send)
            x = ch1.recv()
            if x == 'stop':
                break
            assert x == 'a'
        done.close()
    go(_)

    for i in range(N):
        _, _rx = select(
            (ch1.send, 'a'),
            (ch2.send, 'b'),
        )
        assert (_, _rx) == (0, None)
    ch1.send('stop')
    done.recv()
    assert len_sendq(ch1) == len_recvq(ch1) == 0
    assert len_sendq(ch2) == len_recvq(ch2) == 0


    # blocking 2·recv
    ch1 = chan()
    ch2 = chan()
    done = chan()
    def _():
        for i in range(N):
            waitBlocked(ch1.recv)
            ch1.send('a')
        done.close()
    go(_)

    for i in range(N):
        _, _rx = select(
            ch1.recv,
            ch2.recv,
        )
        assert (_, _rx) == (0, 'a')
    done.recv()
    assert len_sendq(ch1) == len_recvq(ch1) == 0
    assert len_sendq(ch2) == len_recvq(ch2) == 0


    # blocking send/recv
    ch1 = chan()
    ch2 = chan()
    done = chan()
    def _():
        while 1:
            waitBlocked(ch1.send)
            x = ch1.recv()
            if x == 'stop':
                break
            assert x == 'a'
        done.close()
    go(_)

    for i in range(N):
        _, _rx = select(
            (ch1.send, 'a'),
            ch2.recv,
        )
        assert (_, _rx) == (0, None)
    ch1.send('stop')
    done.recv()
    assert len_sendq(ch1) == len_recvq(ch1) == 0
    assert len_sendq(ch2) == len_recvq(ch2) == 0


    # blocking recv/send
    ch1 = chan()
    ch2 = chan()
    done = chan()
    def _():
        for i in range(N):
            waitBlocked(ch1.recv)
            ch1.send('a')
        done.close()
    go(_)

    for i in range(N):
        _, _rx = select(
            ch1.recv,
            (ch2.send, 'b'),
        )
        assert (_, _rx) == (0, 'a')
    done.recv()
    assert len_sendq(ch1) == len_recvq(ch1) == 0
    assert len_sendq(ch2) == len_recvq(ch2) == 0


    # blocking send + nil channel
    z = nilchan
    for i in range(N):
        ch = chan()
        done = chan()
        def _():
            waitBlocked(ch.send)
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
        assert len_sendq(ch) == len_recvq(ch) == 0

    # blocking recv + nil channel
    for i in range(N):
        ch = chan()
        done = chan()
        def _():
            waitBlocked(ch.recv)
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
        assert len_sendq(ch) == len_recvq(ch) == 0


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
        assert len_sendq(ch1) == len_recvq(ch1) == 0
        assert len_sendq(ch2) == len_recvq(ch2) == 0


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
    assert len_sendq(ch1) == len_recvq(ch1) == 0
    assert len_sendq(ch2) == len_recvq(ch2) == 0


# verify that select does not leak references to passed objects.
@mark.skipif(not hasattr(sys, 'getrefcount'),   # skipped e.g. on PyPy
             reason="needs sys.getrefcount")
def test_select_refleak():
    ch1 = chan()
    ch2 = chan()
    obj1 = object()
    obj2 = object()
    tx1 = (ch1.send, obj1)
    tx2 = (ch2.send, obj2)

    # normal exit
    gc.collect()
    nref1 = sys.getrefcount(obj1)
    nref2 = sys.getrefcount(obj2)
    _, _rx = select(
        tx1,        # 0
        tx2,        # 1
        default,    # 2
    )
    assert (_, _rx) == (2, None)
    gc.collect()
    assert sys.getrefcount(obj1) == nref1
    gc.collect()
    assert sys.getrefcount(obj1) == nref2

    # abnormal exit
    with raises(AttributeError) as exc:
        select(
            tx1,        # 0
            tx2,        # 1
            'zzz',      # 2 causes pyselect to panic
        )
    assert exc.value.args == ("'str' object has no attribute '__self__'",)
    gc.collect()
    assert sys.getrefcount(obj1) == nref1
    gc.collect()
    assert sys.getrefcount(obj1) == nref2


# benchmark sync chan send vs recv on select side.
# pyx/nogil mirror is in _golang_test.pyx
def bench_select(b):
    ch1  = chan()
    ch2  = chan()
    done = chan()
    def _():
        while 1:
            _, _rx = select(
                ch1.recv_,   # 0
                ch2.recv_,   # 1
            )
            if _ == 0:
                _, ok = _rx
                if not ok:
                    done.close()
                    return
    go(_)

    _ = (ch1, ch2)
    for i in xrange(b.N):
        ch = _[i%2]
        ch.send(1)

    ch1.close()
    done.recv()


def test_blockforever():
    with panicWhenBlocked():
        _test_blockforever()

def _test_blockforever():
    z = nilchan
    assert len(z) == 0
    assert repr(z) == "nilchan"
    with panics("t: blocks forever"): z.send(0)
    with panics("t: blocks forever"): z.recv()
    with panics("close of nil channel"): z.close()   # to fully cover nilchan ops

    # select{} & nil-channel only
    with panics("t: blocks forever"): select()
    with panics("t: blocks forever"): select((z.send, 0))
    with panics("t: blocks forever"): select(z.recv)
    with panics("t: blocks forever"): select((z.send, 1), z.recv)


# verify chan(dtype=X) functionality.
def test_chan_dtype_invalid():
    with raises(TypeError) as exc:
        chan(dtype="BadType")
    assert exc.value.args == ("pychan: invalid dtype: 'BadType'",)

chantypev = [
    # dtype         obj     zero-obj
    ('object',      'abc',  None),
    ('C.structZ',   None,   None),
    ('C.bool',      True,   False),
    ('C.int',       4,      0),
    ('C.double',    3.14,   0.0),
]

@mark.parametrize('dtype,obj,zobj', chantypev)
def test_chan_dtype(dtype, obj, zobj):
    # py -> py  (pysend/pyrecv; buffered)
    ch = chan(1, dtype=dtype)
    ch.send(obj)
    obj2, ok = ch.recv_()
    assert ok == True
    assert type(obj2) is type(obj)
    assert obj2 == obj

    # send with different type - rejected
    for (dtype2, obj2, _) in chantypev:
        if dtype2 == dtype or dtype == "object":
            continue    # X -> X; object accepts *,
        if (dtype2, dtype) == ('C.int', 'C.double'): # int -> double  ok
            continue
        with raises(TypeError) as exc:
            ch.send(obj2)
        # XXX we can implement vvv, but it will potentially hide cause error
        # XXX (or use raise from?)
        #assert exc.value.args == ("type mismatch: expect %s; got %r" % (dtype, obj2),)
        with raises(TypeError) as exc:
            select((ch.send, obj2))

    # py -> py  (pyclose/pyrecv)
    ch.close()
    obj2, ok = ch.recv_()
    assert ok == False
    assert type(obj2) is type(zobj)
    assert obj2 == zobj

    # below tests are for py <-> c interaction
    if dtype == "object":
        return
    ctype = dtype[2:]  # C.int -> int

    ch = chan(dtype=dtype)  # recreate after close; mode=synchronous

    # recv/send/close via C
    def crecv(ch):
        return getattr(_golang_test, "pychan_%s_recv" % ctype)(ch)
    def csend(ch, obj):
        getattr(_golang_test, "pychan_%s_send" % ctype)(ch, obj)
    def cclose(ch):
        getattr(_golang_test, "pychan_%s_close" % ctype)(ch)

    # py -> c  (pysend/crecv)
    rx = chan()
    def _():
        _ = crecv(ch)
        rx.send(_)
    go(_)
    ch.send(obj)
    obj2 = rx.recv()
    assert type(obj2) is type(obj)
    assert obj2 == obj

    # py -> c  (pyselect/crecv)
    rx = chan()
    def _():
        _ = crecv(ch)
        rx.send(_)
    go(_)
    _, _rx = select(
        (ch.send, obj), # 0
    )
    assert (_, _rx) == (0, None)
    obj2 = rx.recv()
    assert type(obj2) is type(obj)
    assert obj2 == obj

    # py -> c  (pyclose/crecv)
    rx = chan()
    def _():
        _ = crecv(ch)
        rx.send(_)
    go(_)
    ch.close()
    obj2 = rx.recv()
    assert type(obj2) is type(zobj)
    assert obj2 == zobj


    ch = chan(dtype=dtype)  # recreate after close

    # py <- c  (pyrecv/csend)
    def _():
        csend(ch, obj)
    go(_)
    obj2 = ch.recv()
    assert type(obj2) is type(obj)
    assert obj2 == obj

    # py <- c  (pyselect/csend)
    def _():
        csend(ch, obj)
    go(_)
    _, _rx = select(
        ch.recv,        # 0
    )
    assert _ == 0
    obj2 = _rx
    assert type(obj2) is type(obj)
    assert obj2 == obj

    # py <- c  (pyrecv/cclose)
    def _():
        cclose(ch)
    go(_)
    obj2 = ch.recv()
    assert type(obj2) is type(zobj)
    assert obj2 == zobj


@mark.parametrize('dtype', [_[0] for _ in chantypev])
def test_chan_dtype_misc(dtype):
    nilch = chan.nil(dtype)

    # nil repr
    if dtype == "object":
        assert repr(nilch) == "nilchan"
    else:
        assert repr(nilch) == ("chan.nil(%r)" % dtype)

    # optimization: nil[X]() -> always same object
    nilch_ = chan.nil(dtype)
    assert nilch is nilch_
    if dtype == "object":
        assert nilch is nilchan

    assert hash(nilch) == hash(nilchan)
    assert      (nilch == nilch)            # nil[X] == nil[X]
    assert not  (nilch != nilch)
    assert      (nilch == nilchan)          # nil[X] == nil[*]
    assert not  (nilch != nilchan)
    assert      (nilchan == nilch)          # nil[*] == nil[X]
    assert not  (nilchan != nilch)

    # channels can be compared, different channels differ
    assert nilch != None    # just in case
    ch1 = chan(dtype=dtype)
    ch2 = chan(dtype=dtype)
    ch3 = chan()
    assert ch1 != ch2;  assert not (ch1 == ch2);  assert ch1 == ch1; assert not (ch1 != ch1)
    assert ch1 != ch3;  assert not (ch1 == ch3);  assert ch2 == ch2; assert not (ch2 != ch2)
    assert ch2 != ch3;  assert not (ch2 == ch3);  assert ch3 == ch3; assert not (ch3 != ch3)
    assert hash(nilch) != hash(ch1)
    assert hash(nilch) != hash(ch2)
    assert hash(nilch) != hash(ch3)
    assert nilch != ch1;  assert not (nilch == ch1)
    assert nilch != ch2;  assert not (nilch == ch2)
    assert nilch != ch3;  assert not (nilch == ch3)

    # .nil on chan instance     XXX doesn't work (yet ?)
    """
    ch = chan() # non-nil chan object instance
    with raises(AttributeError):
        ch.nil
    """

    # nil[X] vs nil[Y]
    for (dtype2, _, _) in chantypev:
        nilch2 = chan.nil(dtype2)
        # nil[*] stands for untyped nil - it is equal to nil[X] for ∀ X
        if dtype == "object" or dtype2 == "object":
            if dtype != dtype2:
                assert nilch is not nilch2
            assert hash(nilch) == hash(nilch2)
            assert (nilch  == nilch2)   == True
            assert (nilch2 == nilch)    == True
            assert (nilch  != nilch2)   == False
            assert (nilch2 != nilch)    == False
            continue

        # nil[X] == nil[X]
        if dtype == dtype2:
            assert hash(nilch) == hash(nilch2)
            assert (nilch  == nilch2)   == True
            assert (nilch2 == nilch)    == True
            assert (nilch  != nilch2)   == False
            assert (nilch2 != nilch)    == False
            continue

        # nil[X] != nil[Y]
        assert nilch is not nilch2
        assert (nilch  == nilch2)   == False
        assert (nilch2 == nilch)    == False
        assert (nilch  != nilch2)   == True
        assert (nilch2 != nilch)    == True


def test_func():
    # test how @func(cls) works
    # this also implicitly tests just @func, since @func(cls) uses that.

    class MyClass:
        def __init__(self, v):
            self.v = v

    zzz = zzz_orig = 'z'    # `@func(MyClass) def zzz` must not override zzz
    @func(MyClass)
    def zzz(self, v, x=2, **kkkkwww):
        assert self.v == v
        return v + 1
    assert zzz is zzz_orig
    assert zzz == 'z'

    mstatic = mstatic_orig = 'mstatic'
    @func(MyClass)
    @staticmethod
    def mstatic(v):
        assert v == 5
        return v + 1
    assert mstatic is mstatic_orig
    assert mstatic == 'mstatic'

    mcls = mcls_orig = 'mcls'
    @func(MyClass)
    @classmethod
    def mcls(cls, v):
        assert cls is MyClass
        assert v == 7
        return v + 1
    assert mcls is mcls_orig
    assert mcls == 'mcls'

    # FIXME undefined var after `@func(cls) def var` should be not set

    obj = MyClass(4)
    assert obj.zzz(4)       == 4 + 1
    assert obj.mstatic(5)   == 5 + 1
    assert obj.mcls(7)      == 7 + 1

    # this tests that @func (used by @func(cls)) preserves decorated function signature
    assert fmtargspec(MyClass.zzz) == '(self, v, x=2, **kkkkwww)'

    assert MyClass.zzz.__module__       == __name__
    assert MyClass.zzz.__name__         == 'zzz'

    assert MyClass.mstatic.__module__   == __name__
    assert MyClass.mstatic.__name__     == 'mstatic'

    assert MyClass.mcls.__module__      == __name__
    assert MyClass.mcls.__name__        == 'mcls'


# @func overhead at def time.
def bench_def(b):
    for i  in xrange(b.N):
        def _(): pass

def bench_func_def(b):
    for i in xrange(b.N):
        @func
        def _(): pass

# @func overhead at call time.
def bench_call(b):
    def _(): pass
    for i in xrange(b.N):
        _()

def bench_func_call(b):
    @func
    def _(): pass
    for i in xrange(b.N):
        _()


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

    with panics("function nofunc uses defer, but not @func"):
        nofunc()

    # panic in deferred call - all defers are called
    v = []
    @func
    def _():
        defer(lambda: v.append(1))
        defer(lambda: v.append(2))
        defer(lambda: panic(3))
        defer(lambda: v.append(4))

    with panics(3): _()
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

    with panics(2): _()
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
    _()

    # not directly called by deferred func
    v = []
    @func
    def _():
        def f():
            assert recover() is None
            v.append('not recovered')
        defer(lambda: f())

        panic("zzz")

    with panics("zzz"): _()
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


# verify that defer correctly establishes exception chain (even on py2).
def test_defer_excchain():
    # just @func/raise embeds traceback and adds ø chain
    @func
    def _():
        raise RuntimeError("err")
    with raises(RuntimeError) as exci:
        _()

    e = exci.value
    assert type(e) is RuntimeError
    assert e.args == ("err",)
    assert e.__cause__      is None
    assert e.__context__    is None
    if six.PY3: # .__traceback__ for top-level exception is not set on py2
        assert e.__traceback__  is not None
        tb = Traceback(e.__traceback__)
        assert tb[-1].name == "_"

    # exceptions in deferred calls are chained
    def d1():
        raise RuntimeError("d1: aaa")
    @func
    def d2():   # NOTE regular raise inside @func
        1/0     # which initially sets .__context__ to None
    @func
    def d3():
        # d33->d32->d31 subchain that has to be correctly glued with neighbours as:
        # "d4: bbb" -> d33->d32->d31 -> 1/0
        def d31(): raise RuntimeError("d31")
        def d32(): raise RuntimeError("d32")
        def d33(): raise RuntimeError("d33")
        defer(d33)
        defer(d32)
        defer(d31)
    def d4():
        raise RuntimeError("d4: bbb")

    @func
    def _():
        defer(d4)
        defer(d3)
        defer(d2)
        defer(d1)
        raise RuntimeError("err")

    with raises(RuntimeError) as exci:
        _()

    e4 = exci.value
    assert type(e4) is RuntimeError
    assert e4.args == ("d4: bbb",)
    assert e4.__cause__     is None
    assert e4.__context__   is not None
    if six.PY3: # .__traceback__ of top-level exception
        assert e4.__traceback__ is not None
        tb4 = Traceback(e4.__traceback__)
        assert tb4[-1].name == "d4"

    e33 = e4.__context__
    assert type(e33) is RuntimeError
    assert e33.args == ("d33",)
    assert e33.__cause__        is None
    assert e33.__context__      is not None
    assert e33.__traceback__    is not None
    tb33 = Traceback(e33.__traceback__)
    assert tb33[-1].name == "d33"

    e32 = e33.__context__
    assert type(e32) is RuntimeError
    assert e32.args == ("d32",)
    assert e32.__cause__        is None
    assert e32.__context__      is not None
    assert e32.__traceback__    is not None
    tb32 = Traceback(e32.__traceback__)
    assert tb32[-1].name == "d32"

    e31 = e32.__context__
    assert type(e31) is RuntimeError
    assert e31.args == ("d31",)
    assert e31.__cause__        is None
    assert e31.__context__      is not None
    assert e31.__traceback__    is not None
    tb31 = Traceback(e31.__traceback__)
    assert tb31[-1].name == "d31"

    e2 = e31.__context__
    assert type(e2) is ZeroDivisionError
    #assert e2.args == ("division by zero",) # text is different in between py23
    assert e2.__cause__     is None
    assert e2.__context__   is not None
    assert e2.__traceback__ is not None
    tb2 = Traceback(e2.__traceback__)
    assert tb2[-1].name == "d2"

    e1 = e2.__context__
    assert type(e1) is RuntimeError
    assert e1.args == ("d1: aaa",)
    assert e1.__cause__     is None
    assert e1.__context__   is not None
    assert e1.__traceback__ is not None
    tb1 = Traceback(e1.__traceback__)
    assert tb1[-1].name == "d1"

    e = e1.__context__
    assert type(e) is RuntimeError
    assert e.args == ("err",)
    assert e.__cause__      is None
    assert e.__context__    is None
    assert e.__traceback__  is not None
    tb = Traceback(e.__traceback__)
    assert tb[-1].name == "_"

# verify that recover breaks exception chain.
@mark.xfail('PyPy' in sys.version and sys.version_info >= (3,) and sys.pypy_version_info < (7,3),
                reason="https://foss.heptapod.net/pypy/pypy/-/issues/3096")
def test_defer_excchain_vs_recover():
    @func
    def _():
        def p1():
            raise RuntimeError(1)
        defer(p1)
        def p2():
            raise RuntimeError(2)
        defer(p2)
        def _():
            r = recover()
            assert r == "aaa"
        defer(_)
        defer(lambda: panic("aaa"))

    with raises(RuntimeError) as exci:
        _()

    e1 = exci.value
    assert type(e1) is RuntimeError
    assert e1.args == (1,)
    assert e1.__cause__     is None
    assert e1.__context__   is not None
    if six.PY3: # .__traceback__ of top-level exception
        assert e1.__traceback__ is not None
        tb1 = Traceback(e1.__traceback__)
        assert tb1[-1].name == "p1"

    e2 = e1.__context__
    assert type(e2) is RuntimeError
    assert e2.args == (2,)
    assert e2.__cause__     is None
    assert e2.__context__   is None         # not chained to panic
    assert e2.__traceback__ is not None
    tb2 = Traceback(e2.__traceback__)
    assert tb2[-1].name == "p2"

# verify that recover returns exception with .__traceback__ and excchain context set (even on py2).
def test_recover_traceback_and_excchain():
    # raise -> recover
    @func
    def f1():
        def r1():
            e = recover()
            assert e is not None
            assert type(e) is RuntimeError
            assert e.args == ("qqq",)
            assert e.__cause__    is None
            assert e.__context__  is None
            assert e.__suppress_context__ == False
            assert e.__traceback__ is not None
            tb = Traceback(e.__traceback__)
            assert tb[-1].name == "p1"
            assert tb[-2].name == "p2"
            assert tb[-3].name == "p3"
            assert tb[-4].name == "f1"
            # [-5] == _func._
        defer(r1)

        def p1(): raise RuntimeError("qqq")
        def p2(): p1()
        def p3(): p2()
        p3()
    f1()

    # raise -> defer(raise2) -> recover
    @func
    def f2():
        def r2():
            e2 = recover()
            assert e2 is not None
            assert type(e2) is RuntimeError
            assert e2.args == ("epp2",)
            assert e2.__cause__     is None
            assert e2.__context__   is not None
            assert e2.__suppress_context__ == False
            assert e2.__traceback__ is not None
            t2 = Traceback(e2.__traceback__)
            assert t2[-1].name == "pp2"
            # [-2] == _GoFrame.__exit__

            e1 = e2.__context__
            assert type(e1) is RuntimeError
            assert e1.args == ("epp1",)
            assert e1.__cause__     is None
            assert e1.__context__   is None
            assert e1.__suppress_context__ == False
            assert e1.__traceback__ is not None
            t1 = Traceback(e1.__traceback__)
            assert t1[-1].name == "pp1"
            assert t1[-2].name == "f2"
            # [-3] == _func._
        defer(r2)

        def pp2(): raise RuntimeError("epp2")
        defer(pp2)

        def pp1(): raise RuntimeError("epp1")
        pp1()
    f2()

    # raise -> recover -> wrap+reraise
    @func
    def f3():
        def r3():
            e1 = recover()
            assert e1 is not None
            e2 = RuntimeError("bad2")
            e2.__context__  = e1
            raise e2
        defer(r3)

        def bad1(): raise RuntimeError("bad1")
        bad1()

    with raises(RuntimeError) as exci:
        f3()

    e2 = exci.value
    assert type(e2) is RuntimeError
    assert e2.args == ("bad2",)
    assert e2.__cause__     is None
    assert e2.__context__   is not None
    if six.PY3: # .__traceback__ for top-level exception is not set on py2
        assert e2.__traceback__ is not None
        t2 = Traceback(e2.__traceback__)
        assert t2[-1].name == "r3"
    e1 = e2.__context__
    assert type(e1) is RuntimeError
    assert e1.args == ("bad1",)
    assert e1.__cause__     is None
    assert e1.__context__   is None
    assert e1.__traceback__ is not None
    t1 = Traceback(e1.__traceback__)
    assert t1[-1].name == "bad1"
    assert t1[-2].name == "f3"


# verify that traceback.{print_exception,format_exception} work on chained
# exception correctly.
def test_defer_excchain_traceback():
    # tbstr returns traceback that would be printed for exception e.
    def tbstr(e):
        fout_print = six.StringIO()
        traceback.print_exception(type(e), e, e.__traceback__, file=fout_print)
        lout_format = traceback.format_exception(type(e), e, e.__traceback__)
        out_print  = fout_print.getvalue()
        out_format = "".join(lout_format)
        assert out_print == out_format
        return out_print

    # raise without @func/defer - must be printed correctly
    # (we patch traceback.print_exception & co on py2)
    def alpha():
        def beta():
            raise RuntimeError("gamma")
        beta()

    with raises(RuntimeError) as exci:
        alpha()
    e = exci.value
    if not hasattr(e, '__traceback__'): # py2
        e.__traceback__ = exci.tb

    assertDoc("""\
Traceback (most recent call last):
  File "PYGOLANG/golang/golang_test.py", line ..., in test_defer_excchain_traceback
    alpha()
  File "PYGOLANG/golang/golang_test.py", line ..., in alpha
    beta()
  File "PYGOLANG/golang/golang_test.py", line ..., in beta
    raise RuntimeError("gamma")
RuntimeError: gamma
""", tbstr(e))


    # raise in @func/chained defer
    @func
    def caller():
        def q1():
            raise RuntimeError("aaa")
        defer(q1)
        def q2():
            raise RuntimeError("bbb")
        defer(q2)
        raise RuntimeError("ccc")

    with raises(RuntimeError) as exci:
        caller()
    e = exci.value
    if not hasattr(e, '__traceback__'): # py2
        e.__traceback__ = exci.tb

    assertDoc("""\
Traceback (most recent call last):
  File "PYGOLANG/golang/__init__.py", line ..., in _
    return f(*argv, **kw)
  File "PYGOLANG/golang/golang_test.py", line ..., in caller
    raise RuntimeError("ccc")
RuntimeError: ccc

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "PYGOLANG/golang/__init__.py", line ..., in __exit__
    d()
  File "PYGOLANG/golang/golang_test.py", line ..., in q2
    raise RuntimeError("bbb")
RuntimeError: bbb

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "PYGOLANG/golang/golang_test.py", line ..., in test_defer_excchain_traceback
    caller()
  ...
  File "PYGOLANG/golang/__init__.py", line ..., in _
    return f(*argv, **kw)
  File "PYGOLANG/golang/__init__.py", line ..., in __exit__
    d()
  File "PYGOLANG/golang/__init__.py", line ..., in __exit__
    d()
  File "PYGOLANG/golang/golang_test.py", line ..., in q1
    raise RuntimeError("aaa")
RuntimeError: aaa
""", tbstr(e))

    e.__suppress_context__ = True
    assertDoc("""\
Traceback (most recent call last):
  File "PYGOLANG/golang/golang_test.py", line ..., in test_defer_excchain_traceback
    caller()
  ...
  File "PYGOLANG/golang/__init__.py", line ..., in _
    return f(*argv, **kw)
  File "PYGOLANG/golang/__init__.py", line ..., in __exit__
    d()
  File "PYGOLANG/golang/__init__.py", line ..., in __exit__
    d()
  File "PYGOLANG/golang/golang_test.py", line ..., in q1
    raise RuntimeError("aaa")
RuntimeError: aaa
""", tbstr(e))

    e.__cause__ = e.__context__
    assertDoc("""\
Traceback (most recent call last):
  File "PYGOLANG/golang/__init__.py", line ..., in _
    return f(*argv, **kw)
  File "PYGOLANG/golang/golang_test.py", line ..., in caller
    raise RuntimeError("ccc")
RuntimeError: ccc

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "PYGOLANG/golang/__init__.py", line ..., in __exit__
    d()
  File "PYGOLANG/golang/golang_test.py", line ..., in q2
    raise RuntimeError("bbb")
RuntimeError: bbb

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "PYGOLANG/golang/golang_test.py", line ..., in test_defer_excchain_traceback
    caller()
  ...
  File "PYGOLANG/golang/__init__.py", line ..., in _
    return f(*argv, **kw)
  File "PYGOLANG/golang/__init__.py", line ..., in __exit__
    d()
  File "PYGOLANG/golang/__init__.py", line ..., in __exit__
    d()
  File "PYGOLANG/golang/golang_test.py", line ..., in q1
    raise RuntimeError("aaa")
RuntimeError: aaa
""", tbstr(e))


# verify that dump of unhandled chained exception traceback works correctly (even on py2).
def test_defer_excchain_dump():
    # run golang_test_defer_excchain.py and verify its output via doctest.
    tbok = readfile(dir_testprog + "/golang_test_defer_excchain.txt")
    retcode, stdout, stderr = _pyrun(["golang_test_defer_excchain.py"],
                                cwd=dir_testprog, stdout=PIPE, stderr=PIPE)
    assert retcode != 0, (stdout, stderr)
    assert stdout == b""
    assertDoc(tbok, stderr)

# ----//---- (ipython)
def test_defer_excchain_dump_ipython():
    tbok = readfile(dir_testprog + "/golang_test_defer_excchain.txt-ipython")
    retcode, stdout, stderr = _pyrun(["-m", "IPython", "--quick", "--colors=NoColor",
                                "-m", "golang_test_defer_excchain"],
                                envadj={"COLUMNS": "80"}, # force ipython5 avoid thinking termwidth=0
                                cwd=dir_testprog, stdout=PIPE, stderr=PIPE)
    assert retcode == 0, (stdout, stderr)
    # ipython5 uses .pyc for filenames instead of .py
    stdout = re.sub(br'\.pyc\b', b'.py', stdout) # normalize .pyc -> .py
    assertDoc(tbok, stdout)
    assert b"Unknown failure executing module: <golang_test_defer_excchain>" in stderr

# ----//---- (pytest)
def test_defer_excchain_dump_pytest():
    tbok = readfile(dir_testprog + "/golang_test_defer_excchain.txt-pytest")
    retcode, stdout, stderr = _pyrun([
                                # don't let pytest emit internal deprecation warnings to stderr
                                "-W", "ignore::DeprecationWarning",
                                "-m", "pytest", "-o", "python_functions=main",
                                "--tb=short", "golang_test_defer_excchain.py"],
                                cwd=dir_testprog, stdout=PIPE, stderr=PIPE)
    assert retcode != 0, (stdout, stderr)
    assert stderr == b""
    assertDoc(tbok, stdout)


# defer overhead.
def bench_try_finally(b):
    def fin(): pass
    def _():
        try:
            pass
        finally:
            fin()

    for i in xrange(b.N):
        _()

def bench_defer(b):
    def fin(): pass
    @func
    def _():
        defer(fin)

    for i in xrange(b.N):
        _()


# test_error lives in errors_test.py


# verify b, u
def test_strings():
    testv = (
        # bytes          <->            unicode
        (b'',                           u''),
        (b'hello',                      u'hello'),
        (b'hello\nworld',               u'hello\nworld'),
        (b'\xd0\xbc\xd0\xb8\xd1\x80',   u'мир'),

        # invalid utf-8
        (b'\xd0',                       u'\udcd0'),
        (b'a\xd0b',                     u'a\udcd0b'),
        # invalid utf-8 with byte < 0x80
        (b'\xe2\x28\xa1',               u'\udce2(\udca1'),

        # more invalid utf-8
        # https://stackoverflow.com/questions/1301402/example-invalid-utf8-string
        (b"\xc3\x28",                   u'\udcc3('),        # Invalid 2 Octet Sequence
        (b"\xa0\xa1",                   u'\udca0\udca1'),   # Invalid Sequence Identifier
        (b"\xe2\x82\xa1",               u'\u20a1'),         # Valid 3 Octet Sequence '₡'
        (b"\xe2\x28\xa1",               u'\udce2(\udca1'),  # Invalid 3 Octet Sequence (in 2nd Octet)
        (b"\xe2\x82\x28",               u'\udce2\udc82('),  # Invalid 3 Octet Sequence (in 3rd Octet)
        (b"\xf0\x90\x8c\xbc",           u'\U0001033c'),     # Valid 4 Octet Sequence '𐌼'
        (b"\xf0\x28\x8c\xbc",           u'\udcf0(\udc8c\udcbc'), # Invalid 4 Octet Sequence (in 2nd Octet)
        (b"\xf0\x90\x28\xbc",           u'\udcf0\udc90(\udcbc'), # Invalid 4 Octet Sequence (in 3rd Octet)
        (b"\xf0\x28\x8c\x28",           u'\udcf0(\udc8c('), # Invalid 4 Octet Sequence (in 4th Octet)
        (b"\xf8\xa1\xa1\xa1\xa1",                           # Valid 5 Octet Sequence (but not Unicode!)
                                        u'\udcf8\udca1\udca1\udca1\udca1'),
        (b"\xfc\xa1\xa1\xa1\xa1\xa1",                       # Valid 6 Octet Sequence (but not Unicode!)
                                        u'\udcfc\udca1\udca1\udca1\udca1\udca1'),

        # surrogate
        (b'\xed\xa0\x80',               u'\udced\udca0\udc80'),

        # x00 - x1f
        (byterange(0,32),
         u"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f" +
         u"\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f"),

        # non-printable utf-8
        (b'\x7f\xc2\x80\xc2\x81\xc2\x82\xc2\x83\xc2\x84\xc2\x85\xc2\x86\xc2\x87',
                                        u"\u007f\u0080\u0081\u0082\u0083\u0084\u0085\u0086\u0087"),

        # some characters with U >= 0x10000
        (b'\xf0\x9f\x99\x8f',           u'\U0001f64f'),    # 🙏
        (b'\xf0\x9f\x9a\x80',           u'\U0001f680'),    # 🚀
    )

    for tbytes, tunicode in testv:
        assert b(tbytes)   == tbytes
        assert u(tunicode) == tunicode

        assert b(tunicode) == tbytes
        assert u(tbytes)   == tunicode

        assert b(u(tbytes))     == tbytes
        assert u(b(tunicode))   == tunicode


    # invalid types
    with raises(TypeError): b(1)
    with raises(TypeError): u(1)
    with raises(TypeError): b(object())
    with raises(TypeError): u(object())

    # TODO also handle bytearray?

    # b(b(·)) = identity
    _ = b(u'миру мир 123')
    assert isinstance(_, bytes)
    assert b(_) is _

    # u(u(·)) = identity
    _ = u(u'мир труд май')
    assert isinstance(_, unicode)
    assert u(_) is _


def test_qq():
    # NOTE qq is also tested as part of strconv.quote

    # qq(any) returns string type
    assert isinstance(qq(b('мир')), str)    # qq(b) -> str (bytes·py2, unicode·py3)
    assert isinstance(qq( u'мир'),  str)    # qq(u) -> str (bytes·py2, unicode·py3)

    # however what qq returns can be mixed with both unicode and bytes
    assert b'hello %s !' % qq(b('мир')) == b('hello "мир" !')   # b % qq(b)
    assert b'hello %s !' % qq(u('мир')) == b('hello "мир" !')   # b % qq(u) -> b
    assert u'hello %s !' % qq(u('мир')) == u('hello "мир" !')   # u % qq(u)
    assert u'hello %s !' % qq(b('мир')) ==  u'hello "мир" !'    # u % qq(b) -> u

    # custom attributes cannot be injected to what qq returns
    x = qq('мир')
    if not ('PyPy' in sys.version): # https://foss.heptapod.net/pypy/pypy/issues/2763
        with raises(AttributeError):
            x.hello = 1


# ---- misc ----

# _pyrun runs `sys.executable argv... <stdin`.
# it returns exit code, stdout and stderr.
def _pyrun(argv, stdin=None, stdout=None, stderr=None, **kw):   # -> retcode, stdout, stderr
    pyexe = kw.pop('pyexe', sys.executable)
    argv  = [pyexe] + argv

    # adjust $PYTHONPATH to point to pygolang. This makes sure that external
    # script will succeed on `import golang` when running in-tree.
    kw = kw.copy()
    pathv = [dir_pygolang]
    env = kw.pop('env', os.environ.copy())
    envadj = kw.pop('envadj', {})
    env.update(envadj)
    envpath = env.get('PYTHONPATH')
    if envpath is not None:
        pathv.extend(envpath.split(os.pathsep))
    env['PYTHONPATH'] = os.pathsep.join(pathv)

    p = Popen(argv, stdin=(PIPE if stdin else None), stdout=stdout, stderr=stderr, env=env, **kw)
    stdout, stderr = p.communicate(stdin)
    return p.returncode, stdout, stderr

# pyrun runs `sys.executable argv... <stdin`.
# it raises exception if ran command fails.
def pyrun(argv, stdin=None, stdout=None, stderr=None, **kw):
    retcode, stdout, stderr = _pyrun(argv, stdin=stdin, stdout=stdout, stderr=stderr, **kw)
    if retcode:
        raise RuntimeError(' '.join(argv) + '\n' + (stderr and str(stderr) or '(failed)'))
    return stdout

# pyout runs `sys.executable argv... <stdin` and returns its output.
# it raises exception if ran command fails.
def pyout(argv, stdin=None, stdout=PIPE, stderr=None, **kw):
    return pyrun(argv, stdin=stdin, stdout=stdout, stderr=stderr, **kw)

# panics is similar to pytest.raises and asserts that wrapped code panics with arg.
class panics:
    def __init__(self, arg):
        self.arg = arg

    def __enter__(self):
        self.raises = raises(_PanicError)
        self.exc_info = self.raises.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        ok = self.raises.__exit__(exc_type, exc_val, exc_tb)
        if not ok:
            return ok
        # _PanicError raised - let's check panic argument
        assert self.exc_info.value.args == (self.arg,)
        return ok

def test_panics():
    # no panic -> "did not raise"
    with raises(raises.Exception, match="DID NOT RAISE"):
        with panics(""):
            pass

    # raise different type -> exception propagates
    with raises(RuntimeError, match="hello world"):
        with panics(""):
            raise RuntimeError("hello world")

    # panic with different argument
    with raises(AssertionError, match=r"assert \('bbb',\) == \('aaa',\)"):
        with panics("aaa"):
            panic("bbb")

    # panic with expected argument
    with panics(123):
        panic(123)

# assertDoc asserts that want == got via doctest.
#
# in want:
# - PYGOLANG means real pygolang prefix
# - empty lines are changed to <BLANKLINE>
def assertDoc(want, got):
    want = u(want)
    got  = u(got)

    # normalize got to PYGOLANG
    udir_pygolang = abbrev_home(dir_pygolang)    # /home/x/.../pygolang -> ~/.../pygolang
    got = got.replace(dir_pygolang,  "PYGOLANG") # /home/x/.../pygolang -> PYGOLANG
    got = got.replace(udir_pygolang, "PYGOLANG") # ~/.../pygolang       -> PYGOLANG

    # want: process conditionals
    # PY39(...) -> ... if py39 else ø
    py39 = sys.version_info >= (3, 9)
    want = re.sub(r"PY39\((.*)\)", r"\1" if py39 else "", want)

    # want: ^$ -> <BLANKLINE>
    while "\n\n" in want:
        want = want.replace("\n\n", "\n<BLANKLINE>\n")

    X = doctest.OutputChecker()
    if not X.check_output(want, got, doctest.ELLIPSIS):
        # output_difference wants Example object with .want attr
        class Ex: pass
        _ = Ex()
        _.want = want
        fail("not equal:\n" + X.output_difference(_, got,
                    doctest.ELLIPSIS | doctest.REPORT_UDIFF))


# fmtargspec returns formatted arguments for function f.
#
# For example:
#   def f(x, y=3):
#       ...
#   fmtargspec(f) -> '(x, y=3)'
def fmtargspec(f): # -> str
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        return inspect.formatargspec(*inspect.getargspec(f))

def test_fmtargspec():
    def f(x, y=3, z=4, *argv, **kw): pass
    assert fmtargspec(f) == '(x, y=3, z=4, *argv, **kw)'


# readfile returns content of file @path.
def readfile(path):
    with open(path, "r") as f:
        return f.read()

# abbrev_home returns path with user home prefix abbreviated with ~.
def abbrev_home(path):
    home = os.path.expanduser('~')
    if path == home:
        return '~'
    if path.startswith(home+'/'):
        return '~'+path[len(home):]
    return path
