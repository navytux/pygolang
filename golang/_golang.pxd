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
"""_golang.pyx implements golang.pyx - see __init__.pxd for details"""

from libcpp cimport nullptr_t, nullptr as nil

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
cdef extern from "golang.h" namespace "golang" nogil:
    void panic(const char *)
    const char *recover()

    struct _chan
    cppclass chan[T]:
        chan();
        void send(T *ptx)
        void recv(T *prx)
        bint recv_(T *prx)
        void close()
        unsigned len()
        unsigned cap()
        bint operator==(nullptr_t)
        bint operator!=(nullptr_t)
        void operator=(nullptr_t)
        _chan *_rawchan()
    chan[T] makechan[T](unsigned size)

    enum _chanop:
        _CHANSEND
        _CHANRECV
        _CHANRECV_
        _DEFAULT
    struct _selcase:
        _chanop op
        void    *data

    int select(_selcase casev[])

    _selcase _send[T](chan[T] ch, const T *ptx)
    _selcase _recv[T](chan[T] ch, T* prx)
    _selcase _recv_[T](chan[T] ch, T* prx, bint *pok)
    const _selcase _default


# XXX do we need to export py* stuff ?

cpdef pypanic(arg)                  # XXX needed?
cdef void topyexc() except *

# pychan is chan<object>
from cpython cimport PyObject
ctypedef PyObject *pPyObject # https://github.com/cython/cython/issues/534
cdef class pychan:
    cdef chan[pPyObject] ch

# XXX pynilchan, pydefault
#cpdef pyselect(*pycasev)   XXX ?
