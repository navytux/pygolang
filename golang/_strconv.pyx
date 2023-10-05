# -*- coding: utf-8 -*-
# cython: language_level=2
# Copyright (C) 2018-2023  Nexedi SA and Contributors.
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
"""_strconv.pyx implements strconv.pyx - see _strconv.pxd for package overview."""

from __future__ import print_function, absolute_import

import unicodedata, codecs

from golang cimport pyb, byte, rune
from golang cimport _utf8_decode_rune, _xunichr
from golang.unicode cimport utf8

from cpython cimport PyObject, _PyBytes_Resize

cdef extern from "Python.h":
    PyObject* PyBytes_FromStringAndSize(char*, Py_ssize_t) except NULL
    char* PyBytes_AS_STRING(PyObject*)
    void Py_DECREF(PyObject*)


# quote quotes unicode|bytes string into valid "..." bytestring always quoted with ".
cpdef pyquote(s):  # -> bstr
    cdef bint _
    q = _quote(pyb(s), '"', &_)
    return pyb(q)


cdef char[16] hexdigit # = '0123456789abcdef'
for i, c in enumerate('0123456789abcdef'):
    hexdigit[i] = ord(c)


# XXX not possible to use `except (NULL, False)`
#     (https://stackoverflow.com/a/66335433/9456786)
cdef bytes _quote(const byte[::1] s, char quote, bint* out_nonascii_escape): # -> (quoted, nonascii_escape)
    # 2*" + max(4)*each byte (+ 1 for tail \0 implicitly by PyBytesObject)
    cdef Py_ssize_t qmaxsize = 1 + 4*len(s) + 1
    cdef PyObject*  qout     = PyBytes_FromStringAndSize(NULL, qmaxsize)
    cdef byte*      q        = <byte*>PyBytes_AS_STRING(qout)

    cdef bint nonascii_escape = False
    cdef Py_ssize_t i = 0, j
    cdef Py_ssize_t isize
    cdef int size
    cdef rune r
    cdef byte c
    q[0] = quote;  q += 1
    while i < len(s):
        c = s[i]        # XXX -> use raw pointer in the loop
        # fast path - ASCII only
        if c < 0x80:
            if c in (ord('\\'), quote):
                q[0] = ord('\\')
                q[1] = c
                q += 2

            # printable ASCII
            elif 0x20 <= c <= 0x7e:
                q[0] = c
                q += 1

            # non-printable ASCII
            elif c == ord('\t'):
                q[0] = ord('\\')
                q[1] = ord('t')
                q += 2
            elif c == ord('\n'):
                q[0] = ord('\\')
                q[1] = ord('n')
                q += 2
            elif c == ord('\r'):
                q[0] = ord('\\')
                q[1] = ord('r')
                q += 2

            # everything else is non-printable
            else:
                q[0] = ord('\\')
                q[1] = ord('x')
                q[2] = hexdigit[c >> 4]
                q[3] = hexdigit[c & 0xf]
                q += 4

            i += 1

        # slow path - full UTF-8 decoding + unicodedata
        else:
            # XXX optimize non-ascii case
            r, size = _utf8_decode_rune(s[i:])  # XXX -> raw pointer
            isize = i + size

            # decode error - just emit raw byte as escaped
            if r == utf8.RuneError  and  size == 1:
                nonascii_escape = True
                q[0] = ord('\\')
                q[1] = ord('x')
                q[2] = hexdigit[c >> 4]
                q[3] = hexdigit[c & 0xf]
                q += 4

            # printable utf-8 characters go as is
            # XXX ? use Py_UNICODE_ISPRINTABLE (py3, not available on py2)  ?
            # XXX ? and generate C table based on unicodedata for py2 ?
            # XXX -> generate table based on unicodedata for both py2/py3 because Py_UNICODE_ISPRINTABLE is not exactly what matches strconv.IsPrint  (i.e. cat starts from LNPS)
            elif _unicodedata_category(_xunichr(r))[0] in 'LNPS': # letters, numbers, punctuation, symbols
                for j in range(i, isize):
                    q[0] = s[j]
                    q += 1

            # everything else goes in numeric byte escapes
            else:
                nonascii_escape = True
                for j in range(i, isize):
                    c = s[j]
                    q[0] = ord('\\')
                    q[1] = ord('x')
                    q[2] = hexdigit[c >> 4]
                    q[3] = hexdigit[c & 0xf]
                    q += 4

            i = isize

    q[0] = quote;  q += 1
    q[0] = 0;      # don't q++ at last because size does not include tail \0
    cdef Py_ssize_t qsize = (q - <byte*>PyBytes_AS_STRING(qout))
    assert qsize <= qmaxsize
    _PyBytes_Resize(&qout, qsize)

    bqout = <bytes>qout
    Py_DECREF(qout)
    out_nonascii_escape[0] = nonascii_escape
    return bqout


# unquote decodes "-quoted unicode|byte string.
#
# ValueError is raised if there are quoting syntax errors.
def pyunquote(s):  # -> bstr
    us, tail = pyunquote_next(s)
    if len(tail) != 0:
        raise ValueError('non-empty tail after closing "')
    return us

# unquote_next decodes next "-quoted unicode|byte string.
#
# it returns -> (unquoted(s), tail-after-")
#
# ValueError is raised if there are quoting syntax errors.
def pyunquote_next(s):  # -> (bstr, bstr)
    us, tail = _unquote_next(pyb(s))
    return pyb(us), pyb(tail)

cdef _unquote_next(s):
    assert isinstance(s, bytes)

    if len(s) == 0 or s[0:0+1] != b'"':
        raise ValueError('no starting "')

    outv = []
    emit= outv.append

    s = s[1:]
    while 1:
        r, width = _utf8_decode_rune(s)
        if width == 0:
            raise ValueError('no closing "')

        if r == ord('"'):
            s = s[1:]
            break

        # regular UTF-8 character
        if r != ord('\\'):
            emit(s[:width])
            s = s[width:]
            continue

        if len(s) < 2:
            raise ValueError('unexpected EOL after \\')

        c = s[1:1+1]

        # \<c> -> <c>   ; c = \ "
        if c in b'\\"':
            emit(c)
            s = s[2:]
            continue

        # \t \n \r
        uc = None
        if   c == b't':  uc = b'\t'
        elif c == b'n':  uc = b'\n'
        elif c == b'r':  uc = b'\r'
        # accept also \a \b \v \f that Go might produce
        # Python also decodes those escapes even though it does not produce them:
        # https://github.com/python/cpython/blob/2.7.18-0-g8d21aa21f2c/Objects/stringobject.c#L677-L688
        elif c == b'a':  uc = b'\x07'
        elif c == b'b':  uc = b'\x08'
        elif c == b'v':  uc = b'\x0b'
        elif c == b'f':  uc = b'\x0c'

        if uc is not None:
            emit(uc)
            s = s[2:]
            continue

        # \x?? hex
        if c == b'x':   # XXX also handle octals?
            if len(s) < 2+2:
                raise ValueError('unexpected EOL after \\x')

            b = codecs.decode(s[2:2+2], 'hex')
            emit(b)
            s = s[2+2:]
            continue

        raise ValueError('invalid escape \\%s' % chr(ord(c[0:0+1])))

    return b''.join(outv), s


cdef _unicodedata_category = unicodedata.category
