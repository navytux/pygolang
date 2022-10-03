# -*- coding: utf-8 -*-
# Copyright (C) 2018-2022  Nexedi SA and Contributors.
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
"""_golang_str.pyx complements _golang.pyx and keeps everything related to strings.

It is included from _golang.pyx .
"""

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


# __pystr converts obj to str of current python:
#
#   - to bytes,   via b, if running on py2, or
#   - to unicode, via u, if running on py3.
#
# It is handy to use __pystr when implementing __str__ methods.
#
# NOTE __pystr is currently considered to be internal function and should not
# be used by code outside of pygolang.
#
# XXX we should be able to use _pystr, but py3's str verify that it must have
# Py_TPFLAGS_UNICODE_SUBCLASS in its type flags.
cdef __pystr(object obj):
    if PY_MAJOR_VERSION >= 3:
        return pyu(obj)
    else:
        return pyb(obj)


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

# initialize .tp_print for _pystr so that this type could be printed.
# If we don't - printing it will result in `RuntimeError: print recursion`
# because str of this type never reaches real bytes or unicode.
# Do it only on python2, because python3 does not use tp_print at all.
# NOTE _pyunicode does not need this because on py2 str(_pyunicode) returns _pystr.
IF PY2:
    # NOTE Cython does not define tp_print for PyTypeObject - do it ourselves
    from libc.stdio cimport FILE
    cdef extern from "Python.h":
        ctypedef int (*printfunc)(PyObject *, FILE *, int) except -1
        ctypedef struct PyTypeObject:
            printfunc tp_print
        cdef PyTypeObject *Py_TYPE(object)

    cdef int _pystr_tp_print(PyObject *obj, FILE *f, int nesting) except -1:
        o = <bytes>obj
        o = bytes(buffer(o))  # change tp_type to bytes instead of _pystr
        return Py_TYPE(o).tp_print(<PyObject*>o, f, nesting)

    Py_TYPE(_pystr()).tp_print = _pystr_tp_print


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
