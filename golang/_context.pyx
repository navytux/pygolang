# -*- coding: utf-8 -*-
# cython: language_level=2
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
"""_context.pyx implements context.pyx - see _context.pxd for package overview."""

from __future__ import print_function, absolute_import

from golang cimport pychan, pyerror, nil, _interface, gobject, newref, adoptref, topyexc
from golang cimport cxx, time
from cython cimport final, internal
from cython.operator cimport typeid

from libc.math cimport INFINITY
from cpython cimport PyObject, Py_INCREF, Py_DECREF
from libcpp.cast cimport static_cast, dynamic_cast


# _frompyx indicates that a constructur is called from pyx code
cdef object _frompyx = object()

# _newPyCtx creates new PyContext wrapping ctx.
cdef PyContext _newPyCtx(Context ctx):
    cdef PyContext pyctx = PyContext.__new__(PyContext, _frompyx)
    pyctx.ctx       = ctx
    pyctx._pydone   = pychan.from_chan_structZ(ctx.done())
    return pyctx

# Context represents operational context.
#
# A context carries deadline, cancellation signal and immutable context-local
# key -> value dict.
@final
cdef class PyContext:

    @staticmethod
    cdef PyContext from_ctx(Context ctx):
        return _newPyCtx(ctx)

    def __cinit__(PyContext pyctx, object bywho):
        if bywho is not _frompyx:
            raise AssertionError("Context must not be instantiated by user")

    def __dealloc__(PyContext pyctx):
        pyctx.ctx = nil

    # deadline() returns context deadline or None, if there is no deadline.
    def deadline(PyContext pyctx):  # -> time | None
        d = pyctx.ctx.deadline()
        if d == INFINITY:
            return None
        return d

    # done returns channel that is closed when the context is canceled.
    def done(PyContext pyctx):  # -> pychan(dtype='C.structZ')
        return pyctx._pydone

    # err returns None if done is not yet closed, or error that explains why context was canceled.
    def err(PyContext pyctx):   # -> error
        with nogil:
            err = pyctx.ctx.err()
        return pyerror.from_error(err)

    # value returns value associated with key, or None, if context has no key.
    #
    # NOTE keys are compared by object identity, _not_ equality.
    # For example two different object instances that are treated by Python as
    # equal will be considered as _different_ keys.
    def value(PyContext pyctx, object key):  # -> value | None
        cdef _PyValue *_pyvalue
        xvalue = pyctx.ctx.value(<void *>key)
        if xvalue == nil:
            return None
        _pyvalue = dynamic_cast[_pPyValue](xvalue._ptr())
        if _pyvalue == nil:
            raise RuntimeError("value is of unexpected C type: %s" % typeid(xvalue).name())
        return <object>_pyvalue.pyobj

# _PyValue holds python-level value in a context.
ctypedef _PyValue *_pPyValue # https://github.com/cython/cython/issues/534
cdef cppclass _PyValue (_interface, gobject) nogil:
    PyObject *pyobj # holds 1 reference

    __init__(object obj) with gil:
        Py_INCREF(obj)
        this.pyobj = <PyObject*>obj

    void incref():
        gobject.incref()
    void decref():
        cdef _PyValue *self = this  # https://github.com/cython/cython/issues/3233
        if __decref():
            del self
    __dealloc__():
        with gil:
            obj = <object>this.pyobj
            this.pyobj = NULL
            Py_DECREF(obj)


# _newPyCancel creates new _PyCancel wrapping cancel.
cdef _PyCancel _newPyCancel(cancelFunc cancel):
    cdef _PyCancel pycancel = _PyCancel.__new__(_PyCancel, _frompyx)
    pycancel.cancel = cancel
    return pycancel

# _PyCancel wraps C cancel func.
@final
@internal
cdef class _PyCancel:
    cdef cancelFunc cancel

    def __cinit__(_PyCancel pycancel, object bywho):
        if bywho is not _frompyx:
            raise AssertionError("_PyCancel must not be instantiated by user")

    def __dealloc__(_PyCancel pycancel):
        pycancel.cancel = nil

    def __call__(_PyCancel pycancel):
        with nogil:
            pycancel.cancel()


# background returns empty context that is never canceled.
def pybackground(): # -> Context
    return  _pybackground

cdef PyContext _pybackground = _newPyCtx(background())


# canceled is the error returned by Context.err when context is canceled.
pycanceled = pyerror.from_error(canceled)

# deadlineExceeded is the error returned by Context.err when time goes past context's deadline.
pydeadlineExceeded = pyerror.from_error(deadlineExceeded)


# with_cancel creates new context that can be canceled on its own.
#
# Returned context inherits from parent and in particular is canceled when
# parent is done.
#
# The caller should explicitly call cancel to release context resources as soon
# the context is no longer needed.
def pywith_cancel(PyContext pyparent): # -> ctx, cancel
    with nogil:
        _ = with_cancel(pyparent.ctx)
    cdef Context    ctx    = _.first
    cdef cancelFunc cancel = _.second
    return _newPyCtx(ctx), _newPyCancel(cancel)

# with_value creates new context with key=value.
#
# Returned context inherits from parent and in particular has all other
# (key, value) pairs provided by parent.
ctypedef _interface *_pinterface # https://github.com/cython/cython/issues/534
def pywith_value(PyContext pyparent, object key, object value): # -> ctx
    pyvalue = adoptref(new _PyValue(value))
    cdef _interface *_ipyvalue = static_cast[_pinterface](pyvalue._ptr())
    cdef interface  ipyvalue   = <interface>newref(_ipyvalue)
    with nogil:
        ctx = with_value(pyparent.ctx, <void *>key, ipyvalue)
    return _newPyCtx(ctx)

# with_deadline creates new context with deadline.
#
# The deadline of created context is the earliest of provided deadline or
# deadline of parent. Created context will be canceled when time goes past
# context deadline or cancel called, whichever happens first.
#
# The caller should explicitly call cancel to release context resources as soon
# the context is no longer needed.
def pywith_deadline(PyContext pyparent, double deadline): # -> ctx, cancel
    with nogil:
        _ = with_deadline(pyparent.ctx, deadline)
    cdef Context    ctx    = _.first
    cdef cancelFunc cancel = _.second
    return _newPyCtx(ctx), _newPyCancel(cancel)

# with_timeout creates new context with timeout.
#
# it is shorthand for with_deadline(parent, now+timeout).
def pywith_timeout(PyContext pyparent, double timeout): # -> ctx, cancel
    with nogil:
        _ = with_timeout(pyparent.ctx, timeout)
    cdef Context    ctx    = _.first
    cdef cancelFunc cancel = _.second
    return _newPyCtx(ctx), _newPyCancel(cancel)

# merge merges 2 contexts into 1.
#
# The result context:
#
#   - is done when parent1 or parent2 is done, or cancel called, whichever happens first,
#   - has deadline = min(parent1.Deadline, parent2.Deadline),
#   - has associated values merged from parent1 and parent2, with parent1 taking precedence.
#
# Canceling this context releases resources associated with it, so code should
# call cancel as soon as the operations running in this Context complete.
#
# Note: on Go side merge is not part of stdlib context and is provided by
# https://godoc.org/lab.nexedi.com/kirr/go123/xcontext#hdr-Merging_contexts
def pymerge(PyContext parent1, PyContext parent2):  # -> ctx, cancel
    with nogil:
        _ = merge(parent1.ctx, parent2.ctx)
    cdef Context    ctx    = _.first
    cdef cancelFunc cancel = _.second
    return _newPyCtx(ctx), _newPyCancel(cancel)


# ---- for tests ----

def _tctxAssertChildren(PyContext pyctx, set pychildrenOK):
    # pychildrenOK must be set[PyContext]
    for _ in pychildrenOK:
        assert isinstance(_, PyContext)

    cdef cxx.set[Context] childrenOK
    for _ in pychildrenOK:
        childrenOK.insert((<PyContext>_).ctx)

    cdef cxx.set[Context] children = _tctxchildren_pyexc(pyctx.ctx)
    if children != childrenOK:
        raise AssertionError("context children differ") # TODO provide details

cdef cxx.set[Context] _tctxchildren_pyexc(Context ctx) nogil except +topyexc:
    return _tctxchildren(ctx)
