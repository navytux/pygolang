# cython: language_level=2
# Copyright (C) 2019  Nexedi SA and Contributors.
#                     Kirill Smelkov <kirr@nexedi.com>
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
- Python-level panic is represented by pypanic.
"""


from libcpp cimport nullptr_t, nullptr as nil
from libcpp.utility cimport pair
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
        cbool operator==(nullptr_t)         const
        cbool operator!=(nullptr_t)         const
        void operator=(nullptr_t)

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
    struct _selcase:
        _chanop op
        void    *data
        cbool   *rxok
    const _selcase default "golang::_default"

    int select(_selcase casev[])


# ---- python bits ----

cdef void topyexc() except *
cpdef pypanic(arg)

# pychan is chan<object>
from cpython cimport PyObject
ctypedef PyObject *pPyObject # https://github.com/cython/cython/issues/534
from cython cimport final

@final
cdef class pychan:
    cdef chan[pPyObject] ch
