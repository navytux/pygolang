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

pystrconv = None  # = golang.strconv imported at runtime (see __init__.py)

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
    if isinstance(s, bytes):                    # py2: str      py3: bytes
        pass
    elif isinstance(s, unicode):                # py2: unicode  py3: str
        s = _utf8_encode_surrogateescape(s)
    else:
        raise TypeError("b: invalid type %s" % type(s))

    return s

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
    if isinstance(s, unicode):                  # py2: unicode  py3: str
        pass
    elif isinstance(s, bytes):                  # py2: str      py3: bytes
        s = _utf8_decode_surrogateescape(s)
    else:
        raise TypeError("u: invalid type %s" % type(s))

    return s


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


# ---- UTF-8 encode/decode ----

from six import unichr                      # py2: unichr       py3: chr
from six import int2byte as bchr            # py2: chr          py3: lambda x: bytes((x,))

_rune_error = 0xFFFD # unicode replacement character

_ucs2_build        = (sys.maxunicode ==     0xffff)     #    ucs2
assert _ucs2_build or sys.maxunicode >= 0x0010ffff      # or ucs4

# _utf8_decode_rune decodes next UTF8-character from byte string s.
#
# _utf8_decode_rune(s) -> (r, size)
def _utf8_decode_rune(s):
    assert isinstance(s, bytes)

    if len(s) == 0:
        return _rune_error, 0

    l = min(len(s), 4)  # max size of an UTF-8 encoded character
    while l > 0:
        try:
            r = s[:l].decode('utf-8', 'strict')
        except UnicodeDecodeError:
            l -= 1
            continue

        if len(r) == 1:
            return ord(r), l

        # see comment in _utf8_encode_surrogateescape
        if _ucs2_build and len(r) == 2:
            try:
                return _xuniord(r), l
            # e.g. TypeError: ord() expected a character, but string of length 2 found
            except TypeError:
                l -= 1
                continue

        l -= 1
        continue

    # invalid UTF-8
    return _rune_error, 1


# _utf8_decode_surrogateescape mimics s.decode('utf-8', 'surrogateescape') from py3.
def _utf8_decode_surrogateescape(s): # -> unicode
    assert isinstance(s, bytes)
    if PY_MAJOR_VERSION >= 3:
        return s.decode('UTF-8', 'surrogateescape')

    # py2 does not have surrogateescape error handler, and even if we
    # provide one, builtin bytes.decode() does not treat surrogate
    # sequences as error. -> Do the decoding ourselves.
    outv = []
    emit = outv.append

    while len(s) > 0:
        r, width = _utf8_decode_rune(s)
        if r == _rune_error:
            b = ord(s[0])
            assert 0x80 <= b <= 0xff
            emit(unichr(0xdc00 + b))

        # python2 "correctly" decodes surrogates - don't allow that as
        # surrogates are not valid UTF-8:
        # https://github.com/python/cpython/blob/v3.8.1-118-gdbb37aac142/Objects/stringlib/codecs.h#L153-L157
        # (python3 raises UnicodeDecodeError for surrogates)
        elif 0xd800 <= r < 0xdfff:
            for c in s[:width]:
                b = ord(c)
                if c >= 0x80:
                    emit(unichr(0xdc00 + b))
                else:
                    emit(unichr(b))

        else:
            emit(_xunichr(r))

        s = s[width:]

    return u''.join(outv)


# _utf8_encode_surrogateescape mimics s.encode('utf-8', 'surrogateescape') from py3.
def _utf8_encode_surrogateescape(s): # -> bytes
    assert isinstance(s, unicode)
    if PY_MAJOR_VERSION >= 3:
        return s.encode('UTF-8', 'surrogateescape')

    # py2 does not have surrogateescape error handler, and even if we
    # provide one, builtin unicode.encode() does not treat
    # \udc80-\udcff as error. -> Do the encoding ourselves.
    outv = []
    emit = outv.append

    while len(s) > 0:
        uc = s[0]; s = s[1:]
        c = ord(uc)

        if 0xdc80 <= c <= 0xdcff:
            # surrogate - emit unescaped byte
            emit(bchr(c & 0xff))
            continue

        # in builds with --enable-unicode=ucs2 (default for py2 on macos and windows)
        # python represents unicode points > 0xffff as _two_ unicode characters:
        #
        #   uh = u - 0x10000
        #   c1 = 0xd800 + (uh >> 10)      ; [d800, dbff]
        #   c2 = 0xdc00 + (uh & 0x3ff)    ; [dc00, dfff]
        #
        # if detected - merge those two unicode characters for .encode('utf-8') below
        #
        # this should be only relevant for python2, as python3 switched to "flexible"
        # internal unicode representation: https://www.python.org/dev/peps/pep-0393
        if _ucs2_build and (0xd800 <= c <= 0xdbff):
            if len(s) > 0:
                uc2 = s[0]
                c2 = ord(uc2)
                if 0xdc00 <= c2 <= 0xdfff:
                    uc = uc + uc2
                    s = s[1:]

        emit(uc.encode('utf-8', 'strict'))

    return b''.join(outv)


# _xuniord returns ordinal for a unicode character u.
#
# it works correctly even if u is represented as 2 unicode surrogate points on
# ucs2 python build.
if not _ucs2_build:
    _xuniord = ord
else:
    def _xuniord(u):
        assert isinstance(u, unicode)
        if len(u) == 1:
            return ord(u)

        # see _utf8_encode_surrogateescape for details
        if len(u) == 2:
            c1 = ord(u[0])
            c2 = ord(u[1])
            if (0xd800 <= c1 <= 0xdbff) and (0xdc00 <= c2 <= 0xdfff):
                return 0x10000 | ((c1 - 0xd800) << 10) | (c2 - 0xdc00)

        # let it crash
        return ord(u)


# _xunichr returns unicode character for an ordinal i.
#
# it works correctly even on ucs2 python builds, where ordinals >= 0x10000 are
# represented as 2 unicode pointe.
if not _ucs2_build:
    _xunichr = unichr
else:
    def _xunichr(i):
        if i < 0x10000:
            return unichr(i)

        # see _utf8_encode_surrogateescape for details
        uh = i - 0x10000
        return unichr(0xd800 + (uh >> 10)) + \
               unichr(0xdc00 + (uh & 0x3ff))
