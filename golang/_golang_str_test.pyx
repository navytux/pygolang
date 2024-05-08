# -*- coding: utf-8 -*-
# cython: language_level=2
# distutils: language=c++
#
# Copyright (C) 2024  Nexedi SA and Contributors.
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

# helpers for golang_str_test.py that need C-level access.

from cpython cimport PyObject_GetAttr, PyObject_SetAttr, PyObject_DelAttr, PyObject_HasAttr

def CPyObject_GetAttr(obj, attr):           return PyObject_GetAttr(obj, attr)
def CPyObject_SetAttr(obj, attr, v):               PyObject_SetAttr(obj, attr, v)
def CPyObject_DelAttr(obj, attr):                  PyObject_DelAttr(obj, attr)
def CPyObject_HasAttr(obj, attr):           return PyObject_HasAttr(obj, attr)


IF PY3:
    cdef extern from "Python.h":
        int _PyObject_LookupAttr(object obj, object attr, PyObject** pres) except -1

    def CPyObject_LookupAttr(obj, attr):
        cdef PyObject* res
        _PyObject_LookupAttr(obj, attr, &res)
        if res == NULL:
            raise AttributeError((obj, attr))
        return <object>res

# XXX +more capi func
#def CPyObject_GenericGetAttr(obj, attr):    return PyObject_GenericGetAttr(obj, attr)
#def CPyObject_GenericSetAttr(obj, attr, v): PyObject_GenericSetAttr(obj, attr, v)
