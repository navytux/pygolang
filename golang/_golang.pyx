# -*- coding: utf-8 -*-
# cython: language_level=2
# cython: binding=False
# cython: c_string_type=str, c_string_encoding=utf8
# distutils: language = c++
# distutils: depends = libgolang.h
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
"""_golang.pyx provides Python interface to libgolang.{h,cpp}.

See _golang.pxd for package overview.
"""

from __future__ import print_function, absolute_import

# init libgolang runtime & friends early
_init_libgolang()
_init_libpyxruntime()

from cpython cimport PyObject, Py_INCREF, Py_DECREF, PY_MAJOR_VERSION
ctypedef PyObject *pPyObject # https://github.com/cython/cython/issues/534
cdef extern from "Python.h":
    ctypedef struct PyTupleObject:
        PyObject **ob_item
    void Py_FatalError(const char *msg)

from libcpp.vector cimport vector
from cython cimport final

import sys

# ---- panic ----

@final
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
    if arg != nil:
        pyarg = <bytes>arg
        if PY_MAJOR_VERSION >= 3:
            pyarg = pyu(pyarg)
        pypanic(pyarg)

cdef extern from "golang/libgolang.h" nogil:
    const char *recover_ "golang::recover" () except +


# pyrecover needs to clear sys.exc_info().
# py2 has sys.exc_clear() but it was removed in py3.
# provide our own _pysys_exc_clear().
cdef extern from *:
    """
    static void XPySys_ExcClear() {
    #if PY_VERSION_HEX >= 0x03000000 || defined(PYPY_VERSION)
        PyErr_SetExcInfo(NULL, NULL, NULL);
    #else
        PyThreadState *ts;
        PyObject *exc_type, *exc_value, *exc_traceback;

        ts = PyThreadState_GET();
        exc_type        = ts->exc_type;         ts->exc_type        = NULL;
        exc_value       = ts->exc_value;        ts->exc_value       = NULL;
        exc_traceback   = ts->exc_traceback;    ts->exc_traceback   = NULL;

        Py_XDECREF(exc_type);
        Py_XDECREF(exc_value);
        Py_XDECREF(exc_traceback);
    #endif
    }
    """
    void XPySys_ExcClear()
def _pysys_exc_clear():
    XPySys_ExcClear()

# ---- go ----

# go spawns lightweight thread.
#
# go spawns:
#
# - lightweight thread (with    gevent integration), or
# - full OS thread     (without gevent integration).
#
# Use gpython to run Python with integrated gevent, or use gevent directly to do so.
def pygo(f, *argv, **kw):
    _ = _togo(); _.f = f; _.argv = argv; _.kw    = kw
    Py_INCREF(_)    # we transfer 1 ref to _goviac
    with nogil:
        _taskgo_pyexc(_goviac, <void*>_)

@final
cdef class _togo:
    cdef object f
    cdef tuple  argv
    cdef dict   kw

cdef extern from "Python.h" nogil:
    ctypedef struct PyGILState_STATE:
        pass
    PyGILState_STATE PyGILState_Ensure()
    void PyGILState_Release(PyGILState_STATE)

cdef void _goviac(void *arg) nogil:
    # create new py thread state and keep it alive while __goviac runs.
    #
    # Just `with gil` is not enough: for `with gil` if exceptions could be
    # raised inside, cython generates several GIL release/reacquire calls.
    # This way the thread state will be deleted on first release and _new_ one
    # - _another_ thread state - create on acquire. All that implicitly with
    # the effect of loosing things associated with thread state - e.g. current
    # exception.
    #
    # -> be explicit and manually keep py thread state alive ourselves.
    gstate = PyGILState_Ensure() # py thread state will stay alive until PyGILState_Release
    __goviac(arg)
    PyGILState_Release(gstate)

cdef void __goviac(void *arg) nogil:
    with gil:
        try:
            _ = <_togo>arg
            Py_DECREF(_)
            _.f(*_.argv, **_.kw)
        except:
            # ignore exceptions during python interpreter shutdown.
            # python clears sys and other modules at exit which can result in
            # arbitrary exceptions in still alive "daemon" threads that go
            # spawns. Similarly to threading.py(*) we just ignore them.
            #
            # if we don't - there could lots of output like e.g. "lost sys.stderr"
            # and/or "sys.excepthook is missing" etc.
            #
            # (*) github.com/python/cpython/tree/v2.7.16-121-g53639dd55a0/Lib/threading.py#L760-L778
            #     see also "Technical details" in stackoverflow.com/a/12807285/9456786.
            if sys is None:
                return

            raise   # XXX exception -> exit program with traceback (same as in go) ?


# ---- channels ----

@final
cdef class pychan:
    def __cinit__(pychan pych, size=0, dtype=object):
        pych.dtype = parse_dtype(dtype)
        pych._ch = _makechan_pyexc(dtypeRegistry[<int>pych.dtype].size, size)

    # pychan.nil(X) creates new nil pychan with specified dtype.
    # TODO try to avoid exposing .nil on pychan instances, and expose only pychan.nil
    # http://code.activestate.com/recipes/578486-class-only-methods/
    @staticmethod
    def nil(dtype):
        return pychan._nil(dtype)
    @staticmethod
    cdef pychan _nil(object dtype):
        return pynil(parse_dtype(dtype))

    def __dealloc__(pychan pych):
        if pych._ch == nil:
            return

        # pychan[X!=object]: just decref the raw chan and we are done.
        if pych.dtype != DTYPE_PYOBJECT:
            _chanxdecref(pych._ch)
            pych._ch = NULL
            return

        # pychan[object], for now, owns the underlying channel.
        # drain buffered channel to decref sent objects.
        # verify that the channel is not connected anywhere outside us.
        # (if it was present also somewhere else - draining would be incorrect)
        #
        # TODO: in the future there could be multiple pychan[object] wrapping
        # the same underlying raw channel: e.g. ch=chan(); ch2=ch.txonly()
        # -> drain underlying channel only when its last reference goes to 0.
        cdef int refcnt = _chanrefcnt(pych._ch)
        if refcnt != 1:
            # cannot raise py-level exception in __dealloc__
            Py_FatalError("pychan[object].__dealloc__: chan.refcnt=%d ; must be =1" % refcnt)

        cdef chan[pPyObject] ch = _wrapchan[pPyObject](pych._ch)
        _chanxdecref(pych._ch)
        pych._ch = NULL

        cdef PyObject *_rx
        while ch.len() != 0:
            # NOTE *not* chanrecv_pyexc(ch):
            # - recv must not block and must not panic as we verified that we
            #   are the only holder of the channel and that ch buffer is not empty.
            # - even if recv panics, we cannot convert that panic to python
            #   exception in __dealloc__. So if it really panics - let the
            #   panic make it and crash the process similarly to Py_FatalError above.
            _rx = ch.recv()
            Py_DECREF(<object>_rx)

        # ch is decref'ed automatically at return


    # send sends object to a receiver.
    def send(pychan pych, obj):
        cdef chanElemBuf _tx = 0

        if pych.dtype == DTYPE_PYOBJECT:
            # increment obj reference count - until received the channel is
            # holding pointer to the object.
            Py_INCREF(obj)
            (<PyObject **>&_tx)[0] = <PyObject *>obj
        else:
            py_to_c(pych.dtype, obj, &_tx)

        try:
            with nogil:
                _chansend_pyexc(pych._ch, &_tx)
        except: # not only _PanicError as send can also throw e.g. bad_alloc
            # the object was not sent - e.g. it was "send on a closed channel"
            if pych.dtype == DTYPE_PYOBJECT:
                Py_DECREF(obj)
            raise

    # recv_ is "comma-ok" version of recv.
    #
    # ok is true - if receive was delivered by a successful send.
    # ok is false - if receive is due to channel being closed and empty.
    def recv_(pychan pych): # -> (rx, ok)
        cdef chanElemBuf _rx = 0
        cdef bint ok

        with nogil:
            ok = _chanrecv__pyexc(pych._ch, &_rx)

        cdef object rx = None
        cdef PyObject *_rxpy
        if pych.dtype == DTYPE_PYOBJECT:
            _rxpy = (<PyObject **>&_rx)[0]
            if _rxpy != nil:
                # we received the object and the channel dropped pointer to it.
                rx = <object>_rxpy
                Py_DECREF(rx)
        else:
            rx = c_to_py(pych.dtype, &_rx)

        return (rx, ok)

    # recv receives from the channel.
    def recv(pychan pych): # -> rx
        rx, _ = pych.recv_()    # TODO call recv_ via C
        return rx

    # close closes sending side of the channel.
    def close(pychan pych):
        with nogil:
            _chanclose_pyexc(pych._ch)

    def __len__(pychan pych):
        return _chanlen_pyexc(pych._ch)

    def __repr__(pychan pych):
        if pych._ch == nil:
            if pych.dtype == DTYPE_PYOBJECT:
                return "nilchan"
            else:
                return "chan.nil(%r)" % dtypeinfo(pych.dtype).name
        else:
            return super(pychan, pych).__repr__()

    # pychan == pychan
    def __hash__(pychan pych):
        return <Py_hash_t>pych._ch
    # NOTE __ne__ not needed: pychan does not have base class and for that
    # case cython automatically generates __ne__ based on __eq__.
    def __eq__(pychan a, object rhs):
        if not isinstance(rhs, pychan):
            return False
        cdef pychan b = rhs
        if a._ch != b._ch:
            return False
        # a and b point to the same underlying channel object.
        # they compare as same if their types match, or, for nil, additionally,
        # if one of the sides is nil[*] (untyped nil).
        if a.dtype == b.dtype:
            return True
        if a._ch != nil:
            return False
        if a.dtype == DTYPE_PYOBJECT or b.dtype == DTYPE_PYOBJECT:
            return True
        return False


    # pychan -> chan[X]
    # ( should live in "runtime support for channel types" if we could define
    #   methods separate from class )
    cdef nogil:
        chan[structZ]   chan_structZ    (pychan pych):
            pychan_asserttype(pych, DTYPE_STRUCTZ)
            return _wrapchan[structZ](pych._ch)

        chan[cbool]     chan_bool       (pychan pych):
            pychan_asserttype(pych, DTYPE_BOOL)
            return _wrapchan[cbool] (pych._ch)

        chan[int]       chan_int        (pychan pych):
            pychan_asserttype(pych, DTYPE_INT)
            return _wrapchan[int]    (pych._ch)

        chan[double]    chan_double     (pychan pych):
            pychan_asserttype(pych, DTYPE_DOUBLE)
            return _wrapchan[double] (pych._ch)

    # pychan <- chan[X]
    @staticmethod
    cdef pychan from_chan_structZ   (chan[structZ] ch):
        return pychan_from_raw(ch._rawchan(),   DTYPE_STRUCTZ)

    @staticmethod
    cdef pychan from_chan_bool      (chan[cbool] ch):
        return pychan_from_raw(ch._rawchan(),   DTYPE_BOOL)

    @staticmethod
    cdef pychan from_chan_int       (chan[int] ch):
        return pychan_from_raw(ch._rawchan(),   DTYPE_INT)

    @staticmethod
    cdef pychan from_chan_double    (chan[double] ch):
        return pychan_from_raw(ch._rawchan(),   DTYPE_DOUBLE)

cdef void pychan_asserttype(pychan pych, DType dtype) nogil:
    if pych.dtype != dtype:
        panic("pychan: channel type mismatch")

cdef pychan pychan_from_raw(_chan *_ch, DType dtype):
    cdef pychan pych = pychan.__new__(pychan)
    pych.dtype = dtype
    pych._ch   = _ch; _chanxincref(_ch)
    return pych


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
    cdef vector[_selcase] casev = vector[_selcase](n, default)
    cdef pychan pych
    cdef chanElemBuf _rx = 0  # all select recvs are setup to receive into _rx
    cdef cbool rxok = False   # (its ok as only one receive will be actually executed)

    selected = -1
    try:
        # prepare casev for chanselect
        for i in range(n):
            pycase = pycasev[i]
            # default
            if pycase is pydefault:
                casev[i] = default

            # send
            elif type(pycase) is tuple:
                if len(pycase) != 2:
                    pypanic("pyselect: invalid [%d]() case" % len(pycase))
                _tcase = <PyTupleObject *>pycase

                pysend = <object>(_tcase.ob_item[0])
                if pysend.__self__.__class__ is not pychan:
                    pypanic("pyselect: send on non-chan: %r" % (pysend.__self__.__class__,))
                pych = pysend.__self__

                if pysend.__name__ != "send":       # XXX better check PyCFunction directly
                    pypanic("pyselect: send expected: %r" % (pysend,))

                tx = <object>(_tcase.ob_item[1])
                casev[i] = _selsend(pych._ch, nil)
                casev[i].flags = _INPLACE_DATA
                casev[i].user  = pych.dtype

                if pych.dtype == DTYPE_PYOBJECT:
                    # incref tx as if corresponding channel is holding pointer to the object while it is being sent.
                    # we'll decref the object if it won't be sent.
                    # see pychan.send for details.
                    Py_INCREF(tx)
                    (<PyObject **>&casev[i].itxrx)[0] = <PyObject *>tx

                else:
                    # NOTE vvv assumes that size for all dtypes fit into 64 bits
                    py_to_c(pych.dtype, tx, &casev[i].itxrx)  # NOTE can raise exception

            # recv
            else:
                pyrecv = pycase
                if pyrecv.__self__.__class__ is not pychan:
                    pypanic("pyselect: recv on non-chan: %r" % (pyrecv.__self__.__class__,))
                pych = pyrecv.__self__

                if pyrecv.__name__ == "recv":       # XXX better check PyCFunction directly
                    casev[i] = _selrecv(pych._ch, &_rx)
                elif pyrecv.__name__ == "recv_":    # XXX better check PyCFunction directly
                    casev[i] = _selrecv_(pych._ch, &_rx, &rxok)
                else:
                    pypanic("pyselect: recv expected: %r" % (pyrecv,))

                casev[i].user = pych.dtype

        with nogil:
            selected = _chanselect_pyexc(&casev[0], casev.size())

    finally:
        # decref not sent tx (see ^^^ send prepare)
        for i in range(n):
            if casev[i].op == _CHANSEND and casev[i].user == DTYPE_PYOBJECT and (i != selected):
                _tx = (<PyObject **>casev[i].ptx())[0]
                tx  = <object>_tx
                Py_DECREF(tx)

    # return what was selected
    cdef _chanop op = casev[selected].op
    if op == _DEFAULT:
        return selected, None
    if op == _CHANSEND:
        return selected, None

    if op != _CHANRECV:
        raise AssertionError("pyselect: chanselect returned with bad op")

    cdef object rx = None
    cdef PyObject *_rxpy
    cdef DType rxtype = <DType>casev[selected].user
    if rxtype == DTYPE_PYOBJECT:
        # we received nil or the object; if it is object, corresponding channel
        # dropped pointer to it (see pychan.recv_ for details).
        _rxpy = (<PyObject **>&_rx)[0]
        if _rxpy != nil:
            rx = <object>_rxpy
            Py_DECREF(rx)

    else:
        rx = c_to_py(rxtype, &_rx)

    if casev[selected].rxok != nil:
        return selected, (rx, rxok)
    else:
        return selected, rx

# ---- init libgolang runtime ---

cdef extern from "golang/libgolang.h" namespace "golang" nogil:
    struct _libgolang_runtime_ops
    void _libgolang_init(const _libgolang_runtime_ops*)
from cpython cimport PyCapsule_Import

cdef void _init_libgolang() except*:
    # detect whether we are running under gevent or OS threads mode
    # -> use golang.runtime._runtime_(gevent|thread) as libgolang runtime.
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
    # golang module). -> preimport runtimemod via regular import first.
    __import__(runtimemod)
    runtimecaps = (runtimemod + ".libgolang_runtime_ops").encode("utf-8") # py3, cannot use pyb yet
    cdef const _libgolang_runtime_ops *runtime_ops = \
        <const _libgolang_runtime_ops*>PyCapsule_Import(runtimecaps, 0)
    if runtime_ops == nil:
        pypanic("init: %s: libgolang_runtime_ops=nil" % runtimemod)
    _libgolang_init(runtime_ops)


cdef void _init_libpyxruntime() except*:
    # this initializes libpyxruntime and registers its pyatexit hook
    import golang.pyx.runtime


# ---- misc ----

cdef extern from "golang/libgolang.h" namespace "golang" nogil:
    _chan  *_makechan(unsigned elemsize, unsigned size)
    chan[T] _wrapchan[T](_chan *)
    void    _chanxincref(_chan *ch)
    void    _chanxdecref(_chan *ch)
    int     _chanrefcnt(_chan *ch)
    void    _chansend(_chan *ch, const void *ptx)
    bint    _chanrecv_(_chan *ch, void *prx)
    void    _chanclose(_chan *ch)
    unsigned _chanlen(_chan *ch)

    int  _chanselect(_selcase *casev, int casec)
    _selcase _selsend(_chan *ch, const void *ptx)
    _selcase _selrecv(_chan *ch, void *prx)
    _selcase _selrecv_(_chan *ch, void *prx, bint *pok)

    void _taskgo(void (*f)(void *), void *arg)

cdef nogil:

    _chan* _makechan_pyexc(unsigned elemsize, unsigned size)    except +topyexc:
        return _makechan(elemsize, size)

    void _chansend_pyexc(_chan *ch, const void *ptx)            except +topyexc:
        _chansend(ch, ptx)

    bint _chanrecv__pyexc(_chan *ch, void *prx)                 except +topyexc:
        return _chanrecv_(ch, prx)

    void _chanclose_pyexc(_chan *ch)                            except +topyexc:
        _chanclose(ch)

    unsigned _chanlen_pyexc(_chan *ch)                          except +topyexc:
        return _chanlen(ch)

    int _chanselect_pyexc(const _selcase *casev, int casec)     except +topyexc:
        return _chanselect(casev, casec)

    void _taskgo_pyexc(void (*f)(void *) nogil, void *arg)      except +topyexc:
        _taskgo(f, arg)


# ---- runtime support for channel types ----

# chanElemBuf is large enough to keep any dtype.
# NOTE sizeof(chanElemBuf) = max(_.size) from dtypeRegistry (this is checked at
# runtime on module init).
ctypedef uint64_t chanElemBuf

# DTypeInfo provides runtime information for a DType:
# dtype name, element size, py <-> c element conversion routines and typed nil instance.
cdef struct DTypeInfo:
    const char *name    # name of the type, e.g. "C.int"
    unsigned    size

    # py_to_c converts python object to C-level data of dtype.
    # If conversion fails, corresponding exception is raised.
    bint      (*py_to_c)(object obj, chanElemBuf *cto) except False

    # c_to_py converts C-level data into python object according to dtype.
    # The conversion cannot fail, but this can raise exception e.g. due to
    # error when allocating result object.
    object    (*c_to_py) (const chanElemBuf *cfrom)

    # pynil points to pychan instance that represents nil[dtype].
    # it holds one reference and is never freed.
    PyObject   *pynil

# py_to_c converts Python object to C-level data according to dtype.
cdef bint py_to_c(DType dtype, object obj, chanElemBuf *cto) except False:
    dtypei = dtypeinfo(dtype)
    return dtypei.py_to_c(obj, cto)

# c_to_py converts C-level data into Python object according to dtype.
cdef object c_to_py(DType dtype, const chanElemBuf *cfrom):
    dtypei = dtypeinfo(dtype)
    return dtypei.c_to_py(cfrom)

# mkpynil creates pychan instance that represents nil[dtype].
cdef PyObject *mkpynil(DType dtype):
    cdef pychan pynil = pychan.__new__(pychan)
    pynil.dtype = dtype
    pynil._ch   = NULL   # should be already NULL
    Py_INCREF(pynil)
    return <PyObject *>pynil

# pynil returns pychan instance corresponding to nil[dtype].
cdef pychan pynil(DType dtype):
    dtypei = dtypeinfo(dtype)
    return <pychan>dtypei.pynil

# {} dtype -> DTypeInfo.
# XXX const
cdef DTypeInfo[<int>DTYPE_NTYPES] dtypeRegistry

# dtypeinfo returns DTypeInfo corresponding to dtype.
cdef DTypeInfo* dtypeinfo(DType dtype) nogil:
    if not (0 <= dtype < DTYPE_NTYPES):
        # no need to ->pyexc, as this bug means memory corruption and so is fatal
        panic("BUG: pychan dtype invalid")
    return &dtypeRegistry[<int>dtype]

# DTYPE_PYOBJECT
dtypeRegistry[<int>DTYPE_PYOBJECT] = DTypeInfo(
    name        = "object",
    size        = sizeof(PyObject*),
    # py_to_c/c_to_py must not be called for pyobj - as pyobj is the common
    # case, they are manually inlined for speed. The code is also more clear
    # when Py_INCREF/Py_DECREF go in send/recv/select directly.
    py_to_c     = NULL, # must not be called for pyobj
    c_to_py     = NULL, # must not be called for pyobj
    pynil       = mkpynil(DTYPE_PYOBJECT),
)

# pynilchan is nil py channel.
#
# On nil channel: send/recv block forever; close panics.
# pynilchan is alias for pychan.nil(object).
pynilchan = pychan._nil(object)


# DTYPE_STRUCTZ
dtypeRegistry[<int>DTYPE_STRUCTZ] = DTypeInfo(
    name        = "C.structZ",
    size        = 0, # NOTE = _elemsize<structZ>, but _not_ sizeof(structZ) which = 1
    py_to_c     = structZ_py_to_c,
    c_to_py     = structZ_c_to_py,
    pynil       = mkpynil(DTYPE_STRUCTZ),
)

cdef bint structZ_py_to_c(object obj, chanElemBuf *cto) except False:
    # for structZ the only accepted value from python is None
    if obj is not None:
        raise TypeError("type mismatch: expect structZ; got %r" % (obj,))
    # nothing to do - size = 0
    return True

cdef object structZ_c_to_py(const chanElemBuf *cfrom):
    return None


# DTYPE_BOOL
dtypeRegistry[<int>DTYPE_BOOL] = DTypeInfo(
    name        = "C.bool",
    size        = sizeof(cbool),
    py_to_c     = bool_py_to_c,
    c_to_py     = bool_c_to_py,
    pynil       = mkpynil(DTYPE_BOOL),
)

cdef bint bool_py_to_c(object obj, chanElemBuf *cto) except False:
    # don't accept int/double/str/whatever.
    if type(obj) is not bool:
        raise TypeError("type mismatch: expect bool; got %r" % (obj,))
    (<cbool *>cto)[0] = obj # raises *Error if conversion fails
    return True

cdef object bool_c_to_py(const chanElemBuf *cfrom):
    return (<cbool *>cfrom)[0]


# DTYPE_INT
dtypeRegistry[<int>DTYPE_INT] = DTypeInfo(
    name        = "C.int",
    size        = sizeof(int),
    py_to_c     = int_py_to_c,
    c_to_py     = int_c_to_py,
    pynil       = mkpynil(DTYPE_INT),
)

cdef bint int_py_to_c(object obj, chanElemBuf *cto) except False:
    # don't accept bool
    if isinstance(obj, bool):
        raise TypeError("type mismatch: expect int; got %r" % (obj,))
    # don't allow e.g. 3.14 to be implicitly truncated to just 3
    cdef double objf = obj
    if (<int>objf) != objf:
        raise TypeError("type mismatch: expect int; got %r" % (obj,))
    (<int *>cto)[0] = obj # raises *Error if conversion fails
    return True

cdef object int_c_to_py(const chanElemBuf *cfrom):
    return (<int *>cfrom)[0]


# DTYPE_DOUBLE
dtypeRegistry[<int>DTYPE_DOUBLE] = DTypeInfo(
    name        = "C.double",
    size        = sizeof(double),
    py_to_c     = double_py_to_c,
    c_to_py     = double_c_to_py,
    pynil       = mkpynil(DTYPE_DOUBLE),
)

cdef bint double_py_to_c(object obj, chanElemBuf *cto) except False:
    # don't accept bool
    if isinstance(obj, bool):
        raise TypeError("type mismatch: expect float; got %r" % (obj,))
    (<double *>cto)[0] = obj # raises *Error if conversion fails
    return True

cdef object double_c_to_py(const chanElemBuf *cfrom):
    return (<double *>cfrom)[0]


# verify at init time that sizeof(chanElemBuf) = max(_.size)
cdef verify_chanElemBuf():
    cdef int size_max = 0
    for dtype in range(DTYPE_NTYPES):
        size_max = max(size_max, dtypeRegistry[<int>dtype].size)
    if size_max != sizeof(chanElemBuf):
        raise AssertionError("golang: module is miscompiled: max(dtype.size) = %d  ; compiled with = %d" % (size_max, sizeof(chanElemBuf)))
verify_chanElemBuf()

# {} dtype name (str) -> dtype
cdef dict name2dtype = {}
cdef init_name2dtype():
    for dtype in range(DTYPE_NTYPES):
        name2dtype[dtypeRegistry[<int>dtype].name] = dtype
init_name2dtype()

# parse_dtype converts object or string dtype, as e.g. passed to
# pychan(dtype=...) into DType.
cdef DType parse_dtype(dtype) except <DType>-1:
    if dtype is object:
        return DTYPE_PYOBJECT

    _ = name2dtype.get(dtype)
    if _ is None:
        raise TypeError("pychan: invalid dtype: %r" % (dtype,))
    return _


# ---- strings ----

from golang import strconv as pystrconv

def pyb(s): # -> bytes
    """b converts str/unicode/bytes s to UTF-8 encoded bytestring.

       Bytes input is preserved as-is:

          b(bytes_input) == bytes_input

       Unicode input is UTF-8 encoded. The encoding always succeeds.
       b is reverse operation to u - the following invariant is always true:

          b(u(bytes_input)) == bytes_input

       TypeError is raised if type(s) is not one of the above.

       See also: u.
    """
    bs, _ = pystrconv._bstr(s)
    return bs

def pyu(s): # -> unicode
    """u converts str/unicode/bytes s to unicode string.

       Unicode input is preserved as-is:

          u(unicode_input) == unicode_input

       Bytes input is UTF-8 decoded. The decoding always succeeds and input
       information is not lost: non-valid UTF-8 bytes are decoded into
       surrogate codes ranging from U+DC80 to U+DCFF.
       u is reverse operation to b - the following invariant is always true:

          u(b(unicode_input)) == unicode_input

       TypeError is raised if type(s) is not one of the above.

       See also: b.
    """
    us, _ = pystrconv._ustr(s)
    return us

# qq is substitute for %q, which is missing in python.
#
# (python's automatic escape uses smartquotes quoting with either ' or ").
#
# like %s, %q automatically converts its argument to string.
def pyqq(obj):
    # make sure obj is text | bytes
    # py2: unicode | str
    # py3: str     | bytes
    if not isinstance(obj, (unicode, bytes)):
        obj = str(obj)

    qobj = pystrconv.quote(obj)

    # `printf('%s', qq(obj))` should work. For this make sure qobj is always
    # a-la str type (unicode on py3, bytes on py2), that can be transparently
    # converted to unicode or bytes as needed.
    if PY_MAJOR_VERSION >= 3:
        qobj = _pyunicode(pyu(qobj))
    else:
        qobj = _pystr(pyb(qobj))

    return qobj


# XXX cannot `cdef class`: github.com/cython/cython/issues/711
class _pystr(bytes):
    """_str is like bytes but can be automatically converted to Python unicode
    string via UTF-8 decoding.

    The decoding never fails nor looses information - see u for details.
    """

    # don't allow to set arbitrary attributes.
    # won't be needed after switch to -> `cdef class`
    __slots__ = ()


    # __bytes__ - no need
    def __unicode__(self):  return pyu(self)

    def __str__(self):
        if PY_MAJOR_VERSION >= 3:
            return pyu(self)
        else:
            return self


cdef class _pyunicode(unicode):
    """_unicode is like unicode(py2)|str(py3) but can be automatically converted
    to bytes via UTF-8 encoding.

    The encoding always succeeds - see b for details.
    """

    def __bytes__(self):    return pyb(self)
    # __unicode__ - no need

    def __str__(self):
        if PY_MAJOR_VERSION >= 3:
            return self
        else:
            return pyb(self)


# ---- error ----

from golang cimport errors
from libcpp.typeinfo cimport type_info
from cython.operator cimport typeid
from libc.string cimport strcmp

# _frompyx indicates that a constructor is called from pyx code
cdef object _frompyx = object()

cdef class pyerror(Exception):
    # pyerror <- error
    @staticmethod
    cdef object from_error(error err):
        if err == nil:
            return None

        cdef pyerror pyerr = pyerror.__new__(pyerror, _frompyx)
        pyerr.err = err
        return pyerr

    def __cinit__(pyerror pyerr, *argv):
        pyerr.err = nil
        pyerr.args = ()
        if len(argv)==1 and argv[0] is _frompyx:
            return  # keep .err=nil - the object is being created via pyerror.from_error
        pyerr.args = argv

        # pyerror("abc") call
        if type(pyerr) is pyerror:
            arg, = argv
            pyerr.err  = errors_New_pyexc(pyb(arg))
            return

        # class MyError(error); MyError(...)
        # just store .args and be done with it (we already did ^^^)
        pass

    def __dealloc__(pyerror pyerr):
        pyerr.err = nil

    def Error(pyerror pyerr):
        """Error returns string that represents the error."""
        # python-level case
        if type(pyerr) is not pyerror:
            # subclass should override Error, but provide at least something by default
            return repr(pyerr)

        # wrapper around C-level error
        assert pyerr.err != nil
        return pyerr.err.Error()

    def Unwrap(pyerror pyerr):
        """Unwrap tries to extract wrapped error."""
        w = errors_Unwrap_pyexc(pyerr.err)
        return pyerror.from_error(w)

    # pyerror == pyerror
    def __hash__(pyerror pyerr):
        # python-level case
        if type(pyerr) is not pyerror:
            return hash(type(pyerr)) ^ hash(pyerr.args)

        # wrapper around C-level error
        # TODO use std::hash directly
        cdef const type_info* typ = &typeid(pyerr.err._ptr()[0])
        return hash(typ.name()) ^ hash(pyerr.err.Error())
    def __ne__(pyerror a, object rhs):
        return not (a == rhs)
    def __eq__(pyerror a, object rhs):
        if type(a) is not type(rhs):
            return False

        # python-level case
        if type(a) is not pyerror:
            return a.args == rhs.args

        # wrapper around C-level error
        cdef pyerror b = rhs
        cdef const type_info* atype = &typeid(a.err._ptr()[0])
        cdef const type_info* btype = &typeid(b.err._ptr()[0])
        if strcmp(atype.name(), btype.name()) != 0:
            return False

        # XXX hack instead of dynamic == (not available in C++)
        return (a.err.Error() == b.err.Error())


    def __str__(pyerror pyerr):
        return pyerr.Error()

    def __repr__(pyerror pyerr):
        typ = type(pyerr)
        # python-level case
        if typ is not pyerror:
            return "%s.%s%r" % (typ.__module__, typ.__name__, pyerr.args)

        # wrapper around C-level error
        cdef const type_info* ctype = &typeid(pyerr.err._ptr()[0])
        # TODO demangle type name (e.g. abi::__cxa_demangle)
        return "<%s.%s object ctype=%s error=%s>" % (typ.__module__, typ.__name__, ctype.name(), pyqq(pyerr.Error()))


# ---- misc ----

cdef nogil:

    error errors_New_pyexc(const char* text)            except +topyexc:
        return errors.New(text)

    error errors_Unwrap_pyexc(error err)                except +topyexc:
        return errors.Unwrap(err)
