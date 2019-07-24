# -*- coding: utf-8 -*-
# cython: language_level=2
# cython: binding=True
# distutils: language = c++
# distutils: include_dirs = ../3rdparty/include
# distutils: sources = golang.cpp
# distutils: depends = golang.h
#
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

from libc.stdlib cimport malloc, free
from libc.string cimport memset
from libcpp.vector cimport vector

cdef extern from *:
    ctypedef bint cbool "bool"

cdef extern from "golang.h" namespace "golang" nogil:
    void panic(const char *)
    const char *recover() except +

    struct _chan
    cppclass chan[T]:
        _chan *_ch
        chan();
        void send(T *ptx)
        #void send(T tx)
        bint recv_(T *prx)
        void recv(T *prx)
        void close()
        unsigned len()
    chan[T] makechan[T](unsigned size) except +

    enum _chanop:
        _CHANSEND
        _CHANRECV
        _CHANRECV_
        _DEFAULT
    struct _selcase:
        _chanop op
        void    *data

    # XXX not sure how to wrap just select
    int _chanselect(const _selcase *casev, int casec)

    _selcase _send[T](chan[T] ch, const T *ptx)
    _selcase _recv[T](chan[T] ch, T* prx)
    _selcase _recv_[T](chan[T] ch, T* prx, bint *pok)
    const _selcase _default


# ---- python interface ----

from cpython cimport PyObject, Py_INCREF, Py_DECREF

cdef extern from "Python.h":
    ctypedef struct PyTupleObject:
        PyObject **ob_item


# pydefault represents default case for pyselect.
pydefault  = object()

# pynilchan is the nil py channel.
#
# On nil channel: send/recv block forever; close panics.
cdef pychan nilchan = pychan()
free(nilchan.ch._ch)  # XXX vs _ch being shared_ptr ? XXX -> chanfree (free sema)
nilchan.ch._ch = NULL
pynilchan = nilchan

ctypedef PyObject *pPyObject # https://github.com/cython/cython/issues/534

# pychan is chan<object>
cdef class pychan:
    cdef chan[pPyObject] ch

    def __cinit__(pych, size=0):
        pych.ch = makechan[pPyObject](size)

    # send sends object to a receiver.
    def send(pych, obj):
        # increment obj reference count so that obj stays alive until recv
        # wakes up - e.g. even if send wakes up earlier and returns / drops obj reference.
        #
        # in other words: we send to recv obj and 1 reference to it.
        Py_INCREF(obj)

        with nogil:
            _obj = <PyObject *>obj
            chansend_pyexc(pych.ch, &_obj)

    # recv_ is "comma-ok" version of recv.
    #
    # ok is true - if receive was delivered by a successful send.
    # ok is false - if receive is due to channel being closed and empty.
    def recv_(pych): # -> (rx, ok)
        cdef PyObject *_rx = NULL
        cdef bint ok

        with nogil:
            ok = chanrecv__pyexc(pych.ch, &_rx)

        if not ok:
            return (None, ok)

        # we received the object and 1 reference to it.
        rx = <object>_rx    # increfs again
        Py_DECREF(rx)       # since <object> convertion did incref
        return (rx, ok)

    # recv receives from the channel.
    def recv(pych): # -> rx
        rx, _ = pych.recv_()
        return rx

    # close closes sending side of the channel.
    def close(pych):
        chanclose_pyexc(pych.ch)

    def __len__(pych):
        return chanlen_pyexc(pych.ch)

    def __repr__(pych):
        if pych.ch._ch == NULL:
            return "nilchan"
        else:
            return super(pychan, pych).__repr__()


# XXX panic: place = ?

cdef class _PanicError(Exception):
    pass

# panic stops normal execution of current goroutine.
def pypanic(arg):
    raise _PanicError(arg)

# _topyexc converts C-level panic/exc to python panic/exc
cdef void _topyexc() except *:
    # recover is declared `except +` - if it was another - not panic -
    # exception, it will be converted to py exc by cython automatically.
    arg = recover()
    if arg != NULL:
        pypanic(arg)

cdef void chansend_pyexc(chan[pPyObject] ch, PyObject **_ptx)   nogil except +_topyexc:
    ch.send(_ptx)
#cdef void chansend_pyexc(chan[pPyObject] ch, PyObject *_obj)    nogil except +_topyexc:
#    ch.send(_obj)
cdef bint chanrecv__pyexc(chan[pPyObject] ch, PyObject **_prx)  nogil except +_topyexc:
    return ch.recv_(_prx)
cdef void chanclose_pyexc(chan[pPyObject] ch)                   nogil except +_topyexc:
    ch.close()
cdef unsigned chanlen_pyexc(chan[pPyObject] ch)                 nogil except +_topyexc:
    return ch.len()
cdef int _chanselect_pyexc(const _selcase *casev, int casec)    nogil except +_topyexc:
    return _chanselect(casev, casec)


# pyselect executes one ready send or receive channel case.
#
# if no case is ready and default case was provided, select chooses default.
# if no case is ready and default was not provided, select blocks until one case becomes ready.
#
# returns: selected case number and receive info (None if send case was selected).
#
# example:
#
#   _, _rx = select(
#       ch1.recv,           # 0
#       ch2.recv_,          # 1
#       (ch2.send, obj2),   # 2
#       default,            # 3
#   )
#   if _ == 0:
#       # _rx is what was received from ch1
#       ...
#   if _ == 1:
#       # _rx is (rx, ok) of what was received from ch2
#       ...
#   if _ == 2:
#       # we know obj2 was sent to ch2
#       ...
#   if _ == 3:
#       # default case
#       ...
def pyselect(*pycasev):
    cdef int i, n = len(pycasev), selected
    cdef vector[_selcase] casev = vector[_selcase](n)
    cdef pychan pych
    cdef pPyObject _rx = NULL # all select recvs are setup to receive into _rx
    cdef cbool rxok = False   # (its ok as only one receive will be actually executed)
    cdef bint commaok = False # init: silence "used not initialized" warning

    # prepare casev for chanselect
    for i in range(n):
        case = pycasev[i]
        # default
        if case is pydefault:
            casev[i] = _default

        # send
        elif type(case) is tuple:
            if len(case) != 2:
                pypanic("pyselect: invalid [%d]() case" % len(case))
            _tcase = <PyTupleObject *>case

            send = <object>(_tcase.ob_item[0])
            if im_class(send) is not pychan:
                pypanic("pyselect: send on non-chan: %r" % (im_class(send),))
            if send.__func__ is not _pychan_send:
                pypanic("pyselect: send expected: %r" % (send,))

            # quilt ptx through case[1]
            p_tx = &(_tcase.ob_item[1])
            tx   = <object>(p_tx[0])

            pych = send.__self__
            # incref tx; we'll decref it if it won't be sent.
            # see pychan.send for details
            Py_INCREF(tx)
            casev[i] = _send(pych.ch, <pPyObject *>p_tx)

        # recv
        else:
            recv = case
            if im_class(recv) is not pychan:
                pypanic("pyselect: recv on non-chan: %r" % (im_class(recv),))
            if recv.__func__ is _pychan_recv:
                commaok = False
            elif recv.__func__ is _pychan_recv_:
                commaok = True
            else:
                pypanic("pyselect: recv expected: %r" % (recv,))

            pych = recv.__self__
            if commaok:
                casev[i] = _recv_(pych.ch, &_rx, &rxok)
            else:
                casev[i] = _recv(pych.ch, &_rx)

    with nogil:
        #selected = select(casev)
        selected = _chanselect_pyexc(&casev[0], casev.size())

    # decref not sent tx (see ^^^ send prepare)
    for i in range(n):
        if casev[i].op == _CHANSEND and (i != selected):
            p_tx = <PyObject **>casev[i].data
            _tx  = p_tx[0]
            tx   = <object>_tx  # increfs gain
            Py_DECREF(tx)       # for ^^^ <object>
            Py_DECREF(tx)       # for incref at send prepare

    # return what was selected
    cdef _chanop op = casev[selected].op
    if op == _DEFAULT:
        return selected, None
    if op == _CHANSEND:
        return selected, None

    if not (op == _CHANRECV or op == _CHANRECV_):
        raise AssertionError("pyselect: chanselect returned with bad op")
    commaok = (op == _CHANRECV_)
    # we received NULL or the object and 1 reference to it (see pychan.recv_ for details)
    cdef object rx = None
    if _rx != NULL:
        rx = <object>_rx    # increfs again
        Py_DECREF(rx)       # since <object> convertion did incref

    if commaok:
        return selected, (rx, rxok)
    else:
        return selected, rx


# ---- for py tests ----

from golang._pycompat import im_class
import six, time

# unbound pychan.{send,recv,recv_}
_pychan_send  = pychan.send
_pychan_recv  = pychan.recv
_pychan_recv_ = pychan.recv_
if six.PY2:
    # on py3 class.func gets the func; on py2 - unbound_method(func)
    _pychan_send  = _pychan_send.__func__
    _pychan_recv  = _pychan_recv.__func__
    _pychan_recv_ = _pychan_recv_.__func__

cdef extern from "golang.h" nogil:
    bint _tchanblocked(_chan *ch, bint recv, bint send)

# _waitBlocked waits till a receive or send channel operation blocks waiting on the channel.
#
# For example `waitBlocked(ch.send)` waits till sender blocks waiting on ch.
def _waitBlocked(chanop):
    if im_class(chanop) is not pychan:
        pypanic("wait blocked: %r is method of a non-chan: %r" % (chanop, im_class(chanop)))
    cdef pychan pych = chanop.__self__
    cdef bint recv = False
    cdef bint send = False
    if chanop.__func__ is _pychan_recv:
        recv = True
    elif chanop.__func__ is _pychan_send:
        send = True
    else:
        pypanic("wait blocked: unexpected chan method: %r" % (chanop,))

    cdef _chan *_ch = pych.ch._ch
    if _ch == NULL:
        pypanic("wait blocked: called on nil channel")

    t0 = time.time()
    while 1:
        if _tchanblocked(_ch, recv, send):
            return
        now = time.time()
        if now-t0 > 10: # waited > 10 seconds - likely deadlock
            pypanic("deadlock")
        time.sleep(0)   # yield to another thread / coroutine

# ----------------------------------------

"""
from libc.stdio cimport printf

cdef void test() nogil:
    cdef chan a, b
    cdef void *tx = NULL
    cdef void *rx = NULL
    cdef int _

    cdef selcase sel[3]
    sel[0].op   = chansend      XXX -> _selsend     + test via _send/_recv
    sel[0].data = tx
    sel[1].op   = chanrecv          -> _selrecv
    sel[1].data = rx
    sel[2].op   = default
    _ = chanselect(sel, 3)  # XXX 3 -> array_len(sel)

    if _ == 0:
        printf('tx\n')
    if _ == 1:
        printf('rx\n')
    if _ == 2:
        printf('defaut\n')


def xtest():
    with nogil:
        test()
"""
