# -*- coding: utf-8 -*-
# cython: language_level=2
# distutils: language=c++
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

from golang cimport go, chan, _chan, makechan, pychan, nil, select, _send,  \
    _recv, _recv_, _default, panic, pypanic, topyexc

# small tests that verifie pyx-level channel API.
# the work of channels themselves is mostly thoroughly excersized in golang_test.py

import time
#from cpython cimport PY_MAJOR_VERSION
#from golang._pycompat import im_class

# # unbound pychan.{send,recv,recv_}
# _pychan_send  = pychan.send
# _pychan_recv  = pychan.recv
# _pychan_recv_ = pychan.recv_
# if PY_MAJOR_VERSION == 2:
#     # on py3 class.func gets the func; on py2 - unbound_method(func)
#     _pychan_send  = _pychan_send.__func__
#     _pychan_recv  = _pychan_recv.__func__
#     _pychan_recv_ = _pychan_recv_.__func__

cdef extern from "golang/libgolang.h" namespace "golang" nogil:
    int _tchanrecvqlen(_chan *ch)
    int _tchansendqlen(_chan *ch)
    void (*_tblockforever)()

# pylen_{recv,send}q returns len(_chan._{recv,send}q)
def pylen_recvq(pychan pych not None): # -> int
    if pych.ch == nil:
        raise AssertionError('len(.recvq) on nil channel')
    return _tchanrecvqlen(pych.ch._rawchan())
def pylen_sendq(pychan pych not None): # -> int
    if pych.ch == nil:
        raise AssertionError('len(.sendq) on nil channel')
    return _tchansendqlen(pych.ch._rawchan())

# pywaitBlocked waits till a receive or send pychan operation blocks waiting on the channel.
#
# For example `pywaitBlocked(ch.send)` waits till sender blocks waiting on ch.
def pywaitBlocked(pychanop):
    #if im_class(pychanop) is not pychan:
    if pychanop.__self__.__class__ is not pychan:
        pypanic("wait blocked: %r is method of a non-chan: %r" % (pychanop, pychanop.__self__.__class__))
    cdef pychan pych = pychanop.__self__
    cdef bint recv = False
    cdef bint send = False
    #if pychanop.__func__ is _pychan_recv:
    if pychanop.__name__ == "recv":     # XXX better check PyCFunction directly
        recv = True
    #elif pychanop.__func__ is _pychan_send:
    elif pychanop.__name__ == "send":   # XXX better check PyCFunction directly
        send = True
    else:
        pypanic("wait blocked: unexpected chan method: %r" % (pychanop,))

    waitBlocked(pych.ch._rawchan(), recv, send)


# waitBlocked waits until either a receive (if rx) or send (if tx) operation
# blocks waiting on the channel.
cdef void waitBlocked(_chan *ch, bint rx, bint tx) nogil:
    if ch == nil:
        panic("wait blocked: called on nil channel")

    cdef bint deadlock = False

    with gil:
        t0 = time.time()
    while 1:
        if rx and (_tchanrecvqlen(ch) != 0):
            return
        if tx and (_tchansendqlen(ch) != 0):
            return

        with gil:
            now = time.time()
            if now-t0 > 10: # waited > 10 seconds - likely deadlock
                deadload = True
        if deadlock:
            panic("deadlock")
        with gil:
            time.sleep(0)   # yield to another thread / coroutine


# `with pypanicWhenBlocked` hooks into golang _blockforever to raise panic with
# "t: blocks forever" instead of blocking.
cdef class pypanicWhenBlocked:
    def __enter__(t):
        global _tblockforever
        _tblockforever = _panicblocked
        return t

    def __exit__(t, typ, val, tb):
        _tblockforever = NULL

cdef void _panicblocked() nogil:
    panic("t: blocks forever")


cdef extern from *:
    ctypedef bint cbool "bool"

ctypedef struct Point:
    int x
    int y

cdef void _test_chan_nogil() nogil except +topyexc:
    cdef chan[int]   chi = makechan[int](1)
    cdef chan[Point] chp = makechan[Point]()
    chp = nil   # reset to nil

    cdef int i, j
    cdef Point p
    cdef cbool jok

    i=+1; chi.send(&i)
    j=-1; chi.recv(&j)
    if not (j == i):
        panic("send -> recv != I")

    i = 2
    _ = select([
        _send(chi, &i),         # 0
        _recv(chp, &p),         # 1
        _recv_(chi, &j, &jok),  # 2
        _default,               # 3
    ])
    if _ != 0:
        panic("select: selected !0")

    jok = chi.recv_(&j)
    if not (j == 2 and jok == True):
        panic("recv_ != (2, true)")

    chi.close()
    jok = chi.recv_(&j)
    if not (j == 0 and jok == False):
        panic("recv_ from closed != (0, false)")

def test_chan_nogil():
    with nogil:
        _test_chan_nogil()


cdef void _test_go_nogil() nogil except +topyexc:
    cdef chan[void] done = makechan[void]()
    cdef int i = 111
    go(_work, &i, done)
    done.recv(NULL)
    if i != 222:
        panic("after done: i != 222")
cdef void _work(int *pi, chan[void] done) nogil:
    pi[0] = 222
    done.close()

def test_go_nogil():
    with nogil:
        _test_go_nogil()





# runtime/libgolang_test_c.c
cdef extern from *:
    """
    extern "C" void _test_chan_c();
    """
    void _test_chan_c() nogil except +topyexc
def test_chan_c():
    with nogil:
        _test_chan_c()

# runtime/libgolang_test.cpp
cdef extern from *:
    """
    extern void _test_chan_cpp();
    extern void _test_chan_vs_stackdeadwhileparked();
    """
    void _test_chan_cpp() nogil except +topyexc
    void _test_chan_vs_stackdeadwhileparked() nogil except +topyexc
def test_chan_cpp():
    with nogil:
        _test_chan_cpp()
def test_chan_vs_stackdeadwhileparked():
    with nogil:
        _test_chan_vs_stackdeadwhileparked()
