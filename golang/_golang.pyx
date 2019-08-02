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
"""_golang.pyx provides Python interface to golang.{h,cpp}"""

# XXX golang/golang.h or just golang.h ?

from __future__ import print_function, absolute_import

# init libgolang runtime early
_init_libgolang()

from golang._pycompat import im_class

from cpython cimport Py_INCREF, Py_DECREF
cdef extern from "Python.h":
    ctypedef struct PyTupleObject:
        PyObject **ob_item
    int Py_REFCNT(object o)     # XXX temp?

from libcpp.vector cimport vector
cdef extern from *:
    ctypedef bint cbool "bool"




# ---- panic ----

cdef class _PanicError(Exception):
    pass

# panic stops normal execution of current goroutine.
cpdef pypanic(arg):
    raise _PanicError(arg)

# topyexc converts C-level panic/exc to python panic/exc.
# (see usage in e.g. *_pyexc functions in "misc")
cdef void topyexc() except *:
    # TODO use libunwind/libbacktrace/libstacktrace/... to append C-level traceback
    #      from where it panicked till topyexc user.
    # TODO install C-level traceback dump as std::terminate handler.
    #
    # recover_ is declared `except +` - if it was another - not panic -
    # exception, it will be converted to py exc by cython automatically.
    arg = recover_()
    if arg != NULL:
        pypanic(arg)

cdef extern from "golang.h" nogil:
    const char *recover_ "golang::recover" () except +


# ---- channels -----

# pynilchan is the nil py channel.
#
# On nil channel: send/recv block forever; close panics.
cdef pychan _pynilchan = pychan()
_pynilchan.ch = chan[pPyObject]()  # = NULL
pynilchan = _pynilchan

# pychan is chan<object>
cdef class pychan:
    def __cinit__(pych, size=0):
        pych.ch = makechan_pyobj_pyexc(size)

    def __dealloc__(pych):
        # XXX on del: drain buffered channel (to decref sent objects) ?
        pych.ch = nil # does _chanxdecref(ch)

    # send sends object to a receiver.
    def send(pych, obj):
        # increment obj reference count - until received the channel is holding pointer to the object.
        Py_INCREF(obj)
#       print('send %x  refcnt=%d' % (id(obj), Py_REFCNT(obj)))

        try:
            with nogil:
                _obj = <PyObject *>obj
                chansend_pyexc(pych.ch, &_obj)
        except _PanicError:
            # the object was not sent - e.g. it was send on a closed channel
            Py_DECREF(obj)
            raise

#       time.sleep(0.5)
#       print('\tsend wokeup  refcnt=%d' % Py_REFCNT(obj))

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

        # we received the object and the channel droped pointer to it.
        rx = <object>_rx
        Py_DECREF(rx)
        return (rx, ok)

    # recv receives from the channel.
    def recv(pych): # -> rx
        rx, _ = pych.recv_()
#       print('recv %x  refcnt=%d' % (id(rx), Py_REFCNT(rx)))
#       time.sleep(1)
        return rx

    # close closes sending side of the channel.
    def close(pych):
        chanclose_pyexc(pych.ch)

    def __len__(pych):
        return chanlen_pyexc(pych.ch)

    def __repr__(pych):
        if pych.ch == nil:
            return "nilchan"
        else:
            return super(pychan, pych).__repr__()


# pydefault represents default case for pyselect.
pydefault  = object()

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
            # incref tx as if corresponding channel is holding pointer to the object while it is being sent.
            # we'll decref the object if it won't be sent.
            # see pychan.send for details.
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
        selected = _chanselect_pyexc(&casev[0], casev.size())

    # decref not sent tx (see ^^^ send prepare)
    for i in range(n):
        if casev[i].op == _CHANSEND and (i != selected):
            p_tx = <PyObject **>casev[i].data
            _tx  = p_tx[0]
            tx   = <object>_tx
            Py_DECREF(tx)

    # return what was selected
    cdef _chanop op = casev[selected].op
    if op == _DEFAULT:
        return selected, None
    if op == _CHANSEND:
        return selected, None

    if not (op == _CHANRECV or op == _CHANRECV_):
        raise AssertionError("pyselect: chanselect returned with bad op")
    commaok = (op == _CHANRECV_)
    # we received NULL or the object; if it is object, corresponding channel
    # dropped pointer to it (see pychan.recv_ for details).
    cdef object rx = None
    if _rx != NULL:
        rx = <object>_rx
        Py_DECREF(rx)

    if commaok:
        return selected, (rx, rxok)
    else:
        return selected, rx

# ---- init libgolang runtime ---

# XXX detect gevent and use _runtime_gevent instead
#from golang.runtime cimport _runtime_thread
#from golang.runtime import _runtime_thread

cdef extern from "golang/golang.h" namespace "golang" nogil:
    struct _libgolang_runtime_ops
    void _libgolang_init(const _libgolang_runtime_ops*)
from cpython cimport PyCapsule_Import

cdef void _init_libgolang():
    # detect whether we are running under gevent or OS threads mode
    threadmod = "thread"
    if PY_MAJOR_VERSION >= 3:
        threadmod = "_thread"
    t = __import__(threadmod)
    runtime = "thread"
    if "gevent" in t.start_new_thread.__module__:
        runtime = "gevent"
    runtimemod = "golang.runtime." + "_runtime_" + runtime

    # PyCapsule_Import("golang.X") does not work properly while we are in the
    # process of importing golang (it tries to access "X" attribute of half-created
    # golang module. -> preimport runtimemod via regular import first.
    __import__(runtimemod)
    cdef const _libgolang_runtime_ops *runtime_ops = <const _libgolang_runtime_ops*>PyCapsule_Import(
            runtimemod + ".libgolang_runtime_ops", 0)
    if runtime_ops == NULL:
        pypanic("init: %s: NULL libgolang_runtime_ops" % runtimemod)
    _libgolang_init(runtime_ops)



# ---- misc ----

cdef extern from "golang/golang.h" namespace "golang" nogil:
    int _chanselect(_selcase *casev, int casec)

cdef nogil:
    chan[pPyObject] makechan_pyobj_pyexc(unsigned size)    except +topyexc:
        return makechan[pPyObject](size)

    void chansend_pyexc(chan[pPyObject] ch, PyObject **_ptx)   except +topyexc:
        ch.send(_ptx)

cdef bint chanrecv__pyexc(chan[pPyObject] ch, PyObject **_prx)  nogil except +topyexc:
    return ch.recv_(_prx)
cdef void chanclose_pyexc(chan[pPyObject] ch)                   nogil except +topyexc:
    ch.close()
cdef unsigned chanlen_pyexc(chan[pPyObject] ch)                 nogil except +topyexc:
    return ch.len()
cdef int _chanselect_pyexc(const _selcase *casev, int casec)    nogil except +topyexc:
    return _chanselect(casev, casec)



# ---- for py tests ----
# XXX -> separate module?

from cpython cimport PY_MAJOR_VERSION
import time

# unbound pychan.{send,recv,recv_}
_pychan_send  = pychan.send
_pychan_recv  = pychan.recv
_pychan_recv_ = pychan.recv_
if PY_MAJOR_VERSION == 2:
    # on py3 class.func gets the func; on py2 - unbound_method(func)
    _pychan_send  = _pychan_send.__func__
    _pychan_recv  = _pychan_recv.__func__
    _pychan_recv_ = _pychan_recv_.__func__

cdef extern from "golang.h" namespace "golang" nogil:
    int _tchanrecvqlen(_chan *ch)
    int _tchansendqlen(_chan *ch)
    void (*_tblockforever)()

# _len{recv,send}q returns len(_chan._{recv,send}q)
def _lenrecvq(pychan pych not None): # -> int
    if pych.ch == nil:
        raise AssertionError('len(.recvq) on nil channel')
    return _tchanrecvqlen(pych.ch._rawchan())
def _lensendq(pychan pych not None): # -> int
    if pych.ch == nil:
        raise AssertionError('len(.sendq) on nil channel')
    return _tchansendqlen(pych.ch._rawchan())

# _waitBlocked waits till a receive or send channel operation blocks waiting on the channel.
#
# For example `_waitBlocked(ch.send)` waits till sender blocks waiting on ch.
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

    if pych.ch == nil:
        pypanic("wait blocked: called on nil channel")

    t0 = time.time()
    while 1:
        if (_lenrecvq(pych) + _lensendq(pych)) != 0:
            return
        now = time.time()
        if now-t0 > 10: # waited > 10 seconds - likely deadlock
            pypanic("deadlock")
        time.sleep(0)   # yield to another thread / coroutine


# `with _tRaiseWhenBlocked` hooks into golang _blockforever to raise panic with
# "t: blocks forever" instead of blocking.
cdef class _tRaiseWhenBlocked:
    def __enter__(t):
        global _tblockforever
        _tblockforever = _raiseblocked
        return t

    def __exit__(t, typ, val, tb):
        _tblockforever = NULL

cdef void _raiseblocked() nogil:
    panic("t: blocks forever")
