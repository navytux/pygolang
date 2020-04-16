# -*- coding: utf-8 -*-
# cython: language_level=2
# distutils: language=c++
#
# Copyright (C) 2018-2020  Nexedi SA and Contributors.
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

# small tests that verifies pyx-level channel API.
# the work of channels themselves is exercised thoroughly mostly in golang_test.py

from __future__ import print_function, absolute_import

from golang cimport go, chan, _chan, makechan, pychan, nil, select, \
    default, structZ, panic, pypanic, topyexc, cbool
from golang cimport time
from cpython cimport PyObject, PyErr_SetString, PyErr_Clear, PyErr_Occurred

cdef extern from "golang/libgolang.h" namespace "golang" nogil:
    int _tchanrecvqlen(_chan *ch)
    int _tchansendqlen(_chan *ch)
    void (*_tblockforever)()

# pylen_{recv,send}q returns len(_chan._{recv,send}q)
def pylen_recvq(pychan pych not None): # -> int
    if pych._ch == nil:
        raise AssertionError('len(.recvq) on nil channel')
    return _tchanrecvqlen(pych._ch)
def pylen_sendq(pychan pych not None): # -> int
    if pych._ch == nil:
        raise AssertionError('len(.sendq) on nil channel')
    return _tchansendqlen(pych._ch)

# runtime/libgolang_test.cpp
cdef extern from *:
    """
    extern void waitBlocked(golang::_chan *ch, int nrx, int ntx);
    """
    void waitBlocked(_chan *, int nrx, int ntx) nogil except +topyexc

# pywaitBlocked waits till a receive or send pychan operation blocks waiting on the channel.
#
# For example `pywaitBlocked(ch.send)` waits till sender blocks waiting on ch.
def pywaitBlocked(pychanop):
    if pychanop.__self__.__class__ is not pychan:
        pypanic("wait blocked: %r is method of a non-chan: %r" % (pychanop, pychanop.__self__.__class__))
    cdef pychan pych = pychanop.__self__
    cdef int nrecv = 0
    cdef int nsend = 0
    if pychanop.__name__ == "recv":     # XXX better check PyCFunction directly
        nrecv = 1
    elif pychanop.__name__ == "send":   # XXX better check PyCFunction directly
        nsend = 1
    else:
        pypanic("wait blocked: unexpected chan method: %r" % (pychanop,))

    with nogil:
        waitBlocked(pych._ch, nrecv, nsend)


# `with pypanicWhenBlocked` hooks into libgolang _blockforever to raise panic with
# "t: blocks forever" instead of blocking.
cdef class pypanicWhenBlocked:
    def __enter__(pypanicWhenBlocked t):
        global _tblockforever
        _tblockforever = _panicblocked
        return t

    def __exit__(pypanicWhenBlocked t, typ, val, tb):
        global _tblockforever
        _tblockforever = NULL

cdef void _panicblocked() nogil:
    panic("t: blocks forever")


# small test to verify pyx(nogil) channels.
ctypedef struct Point:
    int x
    int y

# TODO kill this and teach Cython to coerce pair[X,Y] -> (X,Y)
cdef (int, cbool) recv_(chan[int] ch) nogil:
    _ = ch.recv_()
    return (_.first, _.second)

cdef void _test_chan_nogil() nogil except +topyexc:
    cdef chan[structZ] done = makechan[structZ]()
    cdef chan[int]     chi  = makechan[int](1)
    cdef chan[Point]   chp  = makechan[Point]()
    chp = nil   # reset to nil

    cdef int i, j
    cdef Point p
    cdef cbool jok

    i=+1; chi.send(i)
    j=-1; j = chi.recv()
    if not (j == i):
        panic("send -> recv != I")

    i = 2
    _=select([
        done.recvs(),           # 0
        chi.sends(&i),          # 1
        chp.recvs(&p),          # 2
        chi.recvs(&j, &jok),    # 3
        default,                # 4
    ])
    if _ != 1:
        panic("select: selected !1")

    j, jok = recv_(chi)
    if not (j == 2 and jok == True):
        panic("recv_ != (2, true)")

    chi.close()
    j, jok = recv_(chi)
    if not (j == 0 and jok == False):
        panic("recv_ from closed != (0, false)")

def test_chan_nogil():
    with nogil:
        _test_chan_nogil()


# small test to verify pyx(nogil) go.
cdef void _test_go_nogil() nogil except +topyexc:
    cdef chan[structZ] done = makechan[structZ]()
    go(_work, 111, done)
    done.recv()
cdef void _work(int i, chan[structZ] done) nogil:
    if i != 111:
        panic("_work: i != 111")
    done.close()

def test_go_nogil():
    with nogil:
        _test_go_nogil()


# verify that runtime calls preserve current Python exception
# ( for example gevent runtime uses python-level calls internally which might
#   interfere with current py state )
def test_runtime_vs_pyexc():
    cdef PyObject *pyexc
    assert PyErr_Occurred() == nil # no exception initially

    # set "current" exception
    PyErr_SetString(RuntimeError, "abc")
    pyexc = PyErr_Occurred()
    assert pyexc != nil
    assert pyexc == PyErr_Occurred()

    # makechan (also tests sema alloc)
    cdef chan[int] ch = makechan[int](1)
    assert PyErr_Occurred() == pyexc

    # chan send/recv (also test sema acquire/release)
    ch.send(3)
    assert PyErr_Occurred() == pyexc
    assert ch.recv() == 3
    assert PyErr_Occurred() == pyexc

    # chan free (also tests sema free)
    ch = nil

    # go
    go(_noop)
    assert PyErr_Occurred() == pyexc

    # sleep
    time.sleep(0.001)
    assert PyErr_Occurred() == pyexc

    # now
    time.now()
    assert PyErr_Occurred() == pyexc

    # clear current exception, or else test driver will see calling us as failure
    PyErr_Clear()
    assert PyErr_Occurred() == nil

cdef void _noop() nogil:
    pass

# runtime/libgolang_test_c.c
cdef extern from * nogil:
    """
    extern "C" void _test_chan_c();
    extern "C" void _test_go_c();
    """
    void _test_chan_c() except +topyexc
    void _test_go_c()   except +topyexc
def test_chan_c():
    with nogil:
        _test_chan_c()
def test_go_c():
    with nogil:
        _test_go_c()

# runtime/libgolang_test.cpp
cdef extern from * nogil:
    """
    extern void _test_chan_cpp_refcount();
    extern void _test_chan_cpp();
    extern void _test_chan_vs_stackdeadwhileparked();
    extern void _test_go_cpp();
    extern void _test_close_wakeup_all_vsrecv();
    extern void _test_close_wakeup_all_vsselect();
    extern void _test_select_win_while_queue();
    extern void _test_select_inplace();
    extern void _test_defer();
    extern void _test_refptr();
    extern void _test_global();
    """
    void _test_chan_cpp_refcount()              except +topyexc
    void _test_chan_cpp()                       except +topyexc
    void _test_chan_vs_stackdeadwhileparked()   except +topyexc
    void _test_go_cpp()                         except +topyexc
    void _test_close_wakeup_all_vsrecv()        except +topyexc
    void _test_close_wakeup_all_vsselect()      except +topyexc
    void _test_select_win_while_queue()         except +topyexc
    void _test_select_inplace()                 except +topyexc
    void _test_defer()                          except +topyexc
    void _test_refptr()                         except +topyexc
    void _test_global()                         except +topyexc
def test_chan_cpp_refcount():
    with nogil:
        _test_chan_cpp_refcount()
def test_chan_cpp():
    with nogil:
        _test_chan_cpp()
def test_chan_vs_stackdeadwhileparked():
    with nogil:
        _test_chan_vs_stackdeadwhileparked()
def test_go_cpp():
    with nogil:
        _test_go_cpp()
def test_close_wakeup_all_vsrecv():
    with nogil:
        _test_close_wakeup_all_vsrecv()
def test_close_wakeup_all_vsselect():
    with nogil:
        _test_close_wakeup_all_vsselect()
def test_select_win_while_queue():
    with nogil:
        _test_select_win_while_queue()
def test_select_inplace():
    with nogil:
        _test_select_inplace()
def test_defer():
    with nogil:
        _test_defer()
def test_refptr():
    with nogil:
        _test_refptr()
def test_global():
    with nogil:
        _test_global()


# helpers for pychan(dtype=X)  py <-> c  tests.
def pychan_structZ_recv(pychan pych):
    with nogil: _pychan_structZ_recv(pych)
    return None
def pychan_structZ_send(pychan pych, obj):
    if obj is not None:
        raise TypeError("cannot convert %r to structZ" % (obj,))
    cdef structZ _
    with nogil:
        _pychan_structZ_send(pych, _)
def pychan_structZ_close(pychan pych):
    with nogil: _pychan_structZ_close(pych)

def pychan_bool_recv(pychan pych):
    with nogil: _ = _pychan_bool_recv(pych)
    return _
def pychan_bool_send(pychan pych, cbool obj):
    with nogil: _pychan_bool_send(pych, obj)
def pychan_bool_close(pychan pych):
    with nogil: _pychan_bool_close(pych)

def pychan_int_recv(pychan pych):
    with nogil: _ = _pychan_int_recv(pych)
    return _
def pychan_int_send(pychan pych, int obj):
    with nogil: _pychan_int_send(pych, obj)
def pychan_int_close(pychan pych):
    with nogil: _pychan_int_close(pych)

def pychan_double_recv(pychan pych):
    with nogil: _ = _pychan_double_recv(pych)
    return _
def pychan_double_send(pychan pych, double obj):
    with nogil: _pychan_double_send(pych, obj)
def pychan_double_close(pychan pych):
    with nogil: _pychan_double_close(pych)


cdef nogil:

    structZ _pychan_structZ_recv(pychan pych)               except +topyexc:
        return pych.chan_structZ().recv()
    void    _pychan_structZ_send(pychan pych, structZ obj)  except +topyexc:
        pych.chan_structZ().send(obj)
    void    _pychan_structZ_close(pychan pych)              except +topyexc:
        pych.chan_structZ().close()

    cbool   _pychan_bool_recv(pychan pych)                  except +topyexc:
        return pych.chan_bool().recv()
    void    _pychan_bool_send(pychan pych, cbool obj)       except +topyexc:
        pych.chan_bool().send(obj)
    void    _pychan_bool_close(pychan pych)                 except +topyexc:
        pych.chan_bool().close()

    int     _pychan_int_recv(pychan pych)                   except +topyexc:
        return pych.chan_int().recv()
    void    _pychan_int_send(pychan pych, int obj)          except +topyexc:
        pych.chan_int().send(obj)
    void    _pychan_int_close(pychan pych)                  except +topyexc:
        pych.chan_int().close()

    double  _pychan_double_recv(pychan pych)                except +topyexc:
        return pych.chan_double().recv()
    void    _pychan_double_send(pychan pych, double obj)    except +topyexc:
        pych.chan_double().send(obj)
    void    _pychan_double_close(pychan pych)               except +topyexc:
        pych.chan_double().close()


# ---- benchmarks ----

# bench_go_nogil mirrors golang_test.py:bench_go
def bench_go_nogil(b):
    cdef int N = b.N
    with nogil:
        _bench_go_nogil(N)

cdef void _bench_go_nogil(int N) nogil except +topyexc:
    cdef chan[int] done = makechan[int]()
    for i in range(N):
        go(_bench_go_nogil__func1, done)
        done.recv()

cdef void _bench_go_nogil__func1(chan[int] done) nogil:
    done.send(1)

# bench_chan_nogil mirrors golang_test.py:bench_chan
def bench_chan_nogil(b):
    cdef int N = b.N
    with nogil:
        _bench_chan_nogil(N)

cdef void _bench_chan_nogil(int N) nogil except +topyexc:
    cdef chan[int]     ch   = makechan[int]()
    cdef chan[structZ] done = makechan[structZ]()

    go(_bench_chan_nogil__func1, ch, done)
    for i in range(N):
        ch.send(1)
    ch.close()
    done.recv()

cdef void _bench_chan_nogil__func1(chan[int] ch, chan[structZ] done) nogil:
    while 1:
        _, ok = recv_(ch)
        if not ok:
            done.close()
            return

# bench_select_nogil mirrors golang_test.py:bench_select
def bench_select_nogil(b):
    cdef int N = b.N
    with nogil:
        _bench_select_nogil(N)

cdef void _bench_select_nogil(int N) nogil except +topyexc:
    cdef chan[int]     ch1  = makechan[int]()
    cdef chan[int]     ch2  = makechan[int]()
    cdef chan[structZ] done = makechan[structZ]()

    go(_bench_select_nogil__func1, ch1, ch2, done)
    for i in range(N):
        if i&1: ch1.send(1)
        else:   ch2.send(1)

    ch1.close()
    done.recv()

cdef void _bench_select_nogil__func1(chan[int] ch1, chan[int] ch2, chan[structZ] done) nogil:
    cdef int   i
    cdef cbool ok

    while 1:
        _ = select([
            ch1.recvs(&i, &ok),    # 0
            ch2.recvs(&i, &ok),    # 1
        ])
        if _ == 0:
            if not ok:
                done.close()
                return
