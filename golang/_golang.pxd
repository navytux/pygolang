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
"""Package golang.pyx provides Go-like features for Cython/nogil and runtime for golang.py.

Cython/nogil API
----------------

- `go` spawns lightweight thread.
- `chan[T]`, `makechan[T]` and `select` provide C-level channels with Go semantic.
- `error` is the interface that represents errors.
- `panic` stops normal execution of current goroutine by throwing a C-level exception.

Everything in Cython/nogil API do not depend on Python runtime and in
particular can be used in nogil code.

See README for thorough overview.
See libgolang.h for API details.
See also package golang.py which provides similar functionality for Python.


Golang.py runtime
-----------------

In addition to Cython/nogil API, golang.pyx provides runtime for golang.py:

- Python-level channels are represented by pychan + pyselect.
- Python-level error is represented by pyerror.
- Python-level panic is represented by pypanic.
"""


from libcpp cimport nullptr_t as Nil, nullptr as nil # golang::nil = nullptr
from libcpp.utility cimport pair
from libc.stdint cimport uint64_t
cdef extern from *:
    ctypedef bint cbool "bool"

# nogil pyx-level golang API.
#
# NOTE even though many functions may panic (= throw C++ exception) nothing is
# annotated with `except +`. Reason: `f() except +` tells Cython to wrap every
# call to f with try/catch and convert C++ exception into Python one. And once
# you have a Python-level exception you are in Python world. However we want
# nogil golang.pyx API to be usable without Python at all.
#
# -> golang.pyx users need to add `except +topyexc` to their functions that are
# on the edge of Python/nogil world.
from libcpp.string cimport string  # golang::string = std::string
cdef extern from "golang/libgolang.h" namespace "golang" nogil:
    void panic(const char *)
    const char *recover()

    void go(...)    # typechecking is done by C

    struct _chan
    cppclass chan[T]:
        chan();

        # send/recv/close
        void send(const T&)                 const
        T recv()                            const
        pair[T, cbool] recv_()              const
        void close()                        const

        # send/recv in select
        _selcase sends(const T *ptx)        const
        _selcase recvs()                    const
        _selcase recvs(T* prx)              const
        _selcase recvs(T* prx, cbool *pok)  const

        # length/capacity
        unsigned len()                      const
        unsigned cap()                      const

        # compare wrt nil; =nil
        cbool operator==(Nil)               const
        cbool operator!=(Nil)               const
        void operator=(Nil)

        # for tests
        _chan *_rawchan()   const

    chan[T] makechan[T]()
    chan[T] makechan[T](unsigned size)

    struct structZ:
        pass

    enum _chanop:
        _CHANSEND
        _CHANRECV
        _DEFAULT
    enum _selflags:
        _INPLACE_DATA
    cppclass _selcase:
        _chan     *ch
        _chanop   op
        unsigned  flags
        unsigned  user
        void      *ptxrx
        uint64_t  itxrx
        cbool     *rxok

        const void *ptx() const
        void *prx() const

    const _selcase default "golang::_default"

    int select(_selcase casev[])


    # memory management of C++ nogil classes
    cppclass refptr[T]:
        # compare wrt nil; =nil
        cbool operator== (Nil)          const
        cbool operator!= (Nil)          const
        void  operator=  (Nil)          const

        # compare wrt refptr; =refptr
        # XXX workaround for https://github.com/cython/cython/issues/1357:
        #     compare by .eq() instead of ==
        #cbool operator== (refptr)       const
        #cbool operator!= (refptr)       const
        #cbool operator=  (refptr)       const
        cbool eq "operator==" (refptr)  const
        cbool ne "operator!=" (refptr)  const

        # get raw pointer
        T* _ptr()                       const

    refptr[T] adoptref[T](T *_obj)
    refptr[T] newref  [T](T *_obj)


    cppclass gobject "golang::object":
        cbool __decref()    # protected
        void  incref()
        int   refcnt() const


    # empty interface ~ interface{}
    cppclass _interface:
        void incref()
        void decref()

    cppclass interface (refptr[_interface]):
        # interface.X = interface->X in C++
        void incref "_ptr()->incref" ()
        void decref "_ptr()->decref" ()


    # error interface
    cppclass _error (_interface):
        string Error()

    cppclass error (refptr[_error]):
        # error.X = error->X in C++
        string Error    "_ptr()->Error" ()


    # error wrapper interface
    cppclass _errorWrapper (_error):
        error Unwrap()

    cppclass errorWrapper (refptr[_errorWrapper]):
        # errorWrapper.X = errorWrapper->X in C++
        error Unwrap    "_ptr()->Unwrap" ()


# ---- python bits ----

cdef void topyexc() except *
cpdef pypanic(arg)

# pychan is python wrapper over chan<object> or chan<structZ|bool|int|double|...>
from cython cimport final

# DType describes type of channel elements.
# TODO consider supporting NumPy dtypes too.
cdef enum DType:
    DTYPE_PYOBJECT   = 0    # chan[object]
    DTYPE_STRUCTZ    = 1    # chan[structZ]
    DTYPE_BOOL       = 2    # chan[bool]
    DTYPE_INT        = 3    # chan[int]
    DTYPE_DOUBLE     = 4    # chan[double]
    DTYPE_NTYPES     = 5

# pychan wraps a channel into python object.
#
# Type of channel can be either channel of python objects, or channel of
# C-level objects. If channel elements are C-level objects, the channel - even
# via pychan wrapper - can be used to interact with nogil world.
#
# There can be multiple pychan(s) wrapping a particular raw channel.
@final
cdef class pychan:
    cdef _chan  *_ch
    cdef DType  dtype # type of channel elements

    # pychan.nil(X) creates new nil pychan with element type X.
    @staticmethod                  # XXX needs to be `cpdef nil()` but cython:
    cdef pychan _nil(object dtype) #  "static cpdef methods not yet supported"

    # chan_X returns ._ch wrapped into typesafe pyx/nogil-level chan[X].
    # chan_X panics if channel type != X.
    # X can be any C-level type, but not PyObject.
    cdef nogil:
        chan[structZ]   chan_structZ    (pychan pych)
        chan[cbool]     chan_bool       (pychan pych)
        chan[int]       chan_int        (pychan pych)
        chan[double]    chan_double     (pychan pych)

    # pychan.from_chan_X returns pychan wrapping pyx/nogil-level chan[X].
    # X can be any C-level type, but not PyObject.
    @staticmethod
    cdef pychan from_chan_structZ   (chan[structZ] ch)
    @staticmethod
    cdef pychan from_chan_bool      (chan[cbool] ch)
    @staticmethod
    cdef pychan from_chan_int       (chan[int] ch)
    @staticmethod
    cdef pychan from_chan_double    (chan[double] ch)


# pyerror wraps an error into python object.
#
# There can be multiple pyerror(s) wrapping a particular raw error object.
# Nil C-level error corresponds to None at Python-level.
#
# Pyerror can be also used as base class for Python-level exception types:
#
#  - objects with type being exact pyerror are treated as wrappers around C-level error.
#  - objects with other types inherited from pyerror are treated as Python-level error.
cdef class pyerror(Exception):
    cdef error    err   # raw error object; nil for Python-level case
    cdef readonly args  # .args for Python-level case

    # pyerror.from_error returns pyerror wrapping pyx/nogil-level error.
    # from_error(nil) -> returns None.
    @staticmethod
    cdef object from_error (error err) # -> pyerror | None
