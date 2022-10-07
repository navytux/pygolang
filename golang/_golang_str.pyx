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

from cpython cimport PyUnicode_AsUnicode, PyUnicode_GetSize, PyUnicode_FromUnicode
from cpython cimport PyUnicode_DecodeUTF8
from cpython cimport PyTypeObject, Py_TYPE, richcmpfunc
from cpython cimport Py_EQ, Py_NE, Py_LT, Py_GT, Py_LE, Py_GE
from cpython.iterobject cimport PySeqIter_New
from cpython cimport PyObject_CheckBuffer
cdef extern from "Python.h":
    void PyType_Modified(PyTypeObject *)

cdef extern from "Python.h":
    ctypedef int (*initproc)(object, PyObject *, PyObject *) except -1
    ctypedef struct _XPyTypeObject "PyTypeObject":
        initproc  tp_init

from libc.stdint cimport uint8_t

pystrconv = None  # = golang.strconv imported at runtime (see __init__.py)
import types as pytypes
import functools as pyfunctools
if PY_MAJOR_VERSION >= 3:
    import copyreg as pycopyreg
else:
    import copy_reg as pycopyreg


def pyb(s): # -> bstr
    """b converts object to bstr.

       - For bstr the same object is returned.
       - For bytes, bytearray, or object with buffer interface, the data is
         preserved as-is and only result type is changed to bstr.
       - For ustr/unicode the data is UTF-8 encoded. The encoding always succeeds.

       TypeError is raised if type(s) is not one of the above.

       b is reverse operation to u - the following invariant is always true:

          b(u(bytes_input))  is bstr with the same data as bytes_input.

       See also: u, bstr/ustr.
    """
    bs = _pyb(pybstr, s)
    if bs is None:
        raise TypeError("b: invalid type %s" % type(s))
    return bs

def pyu(s): # -> ustr
    """u converts object to ustr.

       - For ustr the same object is returned.
       - For unicode the data is preserved as-is and only result type is changed to ustr.
       - For bstr, bytes, bytearray, or object with buffer interface, the data is UTF-8 decoded.
         The decoding always succeeds and input
         information is not lost: non-valid UTF-8 bytes are decoded into
         surrogate codes ranging from U+DC80 to U+DCFF.

       TypeError is raised if type(s) is not one of the above.

       u is reverse operation to b - the following invariant is always true:

          u(b(unicode_input))  is ustr with the same data as unicode_input.

       See also: b, bstr/ustr.
    """
    us = _pyu(pyustr, s)
    if us is None:
        raise TypeError("u: invalid type %s" % type(s))
    return us


cdef _pyb(bcls, s): # -> ~bstr | None
    if type(s) is bcls:
        return s

    if isinstance(s, bytes):
        if type(s) is not bytes:
            s = _bdata(s)
    elif isinstance(s, unicode):
        s = _utf8_encode_surrogateescape(s)
    else:
        s = _ifbuffer_data(s) # bytearray and buffer
        if s is None:
            return None

    assert type(s) is bytes
    return bytes.__new__(bcls, s)

cdef _pyu(ucls, s): # -> ~ustr | None
    if type(s) is ucls:
        return s

    if isinstance(s, unicode):
        if type(s) is not unicode:
            s = _udata(s)
    else:
        _ = _ifbuffer_data(s) # bytearray and buffer
        if _ is not None:
            s = _
        if isinstance(s, bytes):
            s = _utf8_decode_surrogateescape(s)
        else:
            return None

    assert type(s) is unicode
    return unicode.__new__(ucls, s)

# _ifbuffer_data returns contained data if obj provides buffer interface.
cdef _ifbuffer_data(obj): # -> bytes|None
    if PyObject_CheckBuffer(obj):
        if PY_MAJOR_VERSION >= 3:
            return bytes(obj)
        else:
            # py2: bytes(memoryview)  returns  '<memory at ...>'
            return bytes(bytearray(obj))
    elif _XPyObject_CheckOldBuffer(obj):  # old-style buffer, py2-only
        return bytes(_buffer_py2(obj))
    else:
        return None


# _pyb_coerce coerces x from `b op x` to be used in operation with pyb.
cdef _pyb_coerce(x):  # -> bstr|bytes
    if isinstance(x, bytes):
        return x
    elif isinstance(x, (unicode, bytearray)):
        return pyb(x)
    else:
        raise TypeError("b: coerce: invalid type %s" % type(x))

# _pyu_coerce coerces x from `u op x` to be used in operation with pyu.
cdef _pyu_coerce(x):  # -> ustr|unicode
    if isinstance(x, unicode):
        return x
    elif isinstance(x, (bytes, bytearray)):
        return pyu(x)
    else:
        raise TypeError("u: coerce: invalid type %s" % type(x))


# __pystr converts obj to ~str of current python:
#
#   - to ~bytes,   via b, if running on py2, or
#   - to ~unicode, via u, if running on py3.
#
# It is handy to use __pystr when implementing __str__ methods.
#
# NOTE __pystr is currently considered to be internal function and should not
# be used by code outside of pygolang.
#
# XXX we should be able to use pybstr, but py3's str verify that it must have
# Py_TPFLAGS_UNICODE_SUBCLASS in its type flags.
cdef __pystr(object obj): # -> ~str
    if PY_MAJOR_VERSION >= 3:
        return pyu(obj)
    else:
        return pyb(obj)


def pybbyte(int i): # -> 1-byte bstr
    """bbyte(i) returns 1-byte bstr with ordinal i."""
    return pyb(bytearray([i]))

def pyuchr(int i):  # -> 1-character ustr
    """uchr(i) returns 1-character ustr with unicode ordinal i."""
    return pyu(unichr(i))


# XXX cannot `cdef class`: github.com/cython/cython/issues/711
class pybstr(bytes):
    """bstr is byte-string.

    It is based on bytes and can automatically convert to/from unicode.
    The conversion never fails and never looses information:

        bstr → ustr → bstr

    is always identity even if bytes data is not valid UTF-8.

    Semantically bstr is array of bytes. Accessing its elements by [index]
    yields byte character. Iterating through bstr, however, yields unicode
    characters. In practice bstr is enough 99% of the time, and ustr only
    needs to be used for random access to string characters. See
    https://blog.golang.org/strings for overview of this approach.

    Operations in between bstr and ustr/unicode / bytes/bytearray coerce to bstr.
    When the coercion happens, bytes and bytearray, similarly to bstr, are also
    treated as UTF8-encoded strings.

    bstr constructor accepts arbitrary objects and stringify them:

    - if encoding and/or errors is specified, the object must provide buffer
      interface. The data in the buffer is decoded according to provided
      encoding/errors and further encoded via UTF-8 into bstr.
    - if the object is bstr/ustr / unicode/bytes/bytearray - it is converted
      to bstr. See b for details.
    - otherwise bstr will have string representation of the object.

    See also: b, ustr/u.
    """

    # don't allow to set arbitrary attributes.
    # won't be needed after switch to -> `cdef class`
    __slots__ = ()

    def __new__(cls, object='', encoding=None, errors=None):
        # encoding or errors  ->  object must expose buffer interface
        if not (encoding is None and errors is None):
            object = _buffer_decode(object, encoding, errors)

        # _bstringify. Note: it handles bstr/ustr / unicode/bytes/bytearray as documented
        object = _bstringify(object)
        assert isinstance(object, (unicode, bytes)), object
        bobj = _pyb(cls, object)
        assert bobj is not None
        return bobj


    def __bytes__(self):    return self
    def __unicode__(self):  return pyu(self)

    def __str__(self):
        if PY_MAJOR_VERSION >= 3:
            return pyu(self)
        else:
            return self


    # override reduce for protocols < 2. Builtin handler for that goes through
    # copyreg._reduce_ex which eventually calls bytes(bstr-instance) to
    # retrieve state, which gives bstr, not bytes. Fix state to be bytes ourselves.
    def __reduce_ex__(self, protocol):
        if protocol >= 2:
            return bytes.__reduce_ex__(self, protocol)
        return (
            pycopyreg._reconstructor,
            (self.__class__, self.__class__, _bdata(self))
        )


    def __hash__(self):
        # hash of the same unicode and UTF-8 encoded bytes is generally different
        # -> we can't make hash(bstr) == both hash(bytes) and hash(unicode) at the same time.
        # -> make hash(bstr) == hash(str type of current python) so that bstr
        #    could be used as keys in dictionary interchangeably with native str type.
        if PY_MAJOR_VERSION >= 3:
            return hash(pyu(self))
        else:
            return bytes.__hash__(self)

    # == != < > <= >=
    # NOTE == and != are special: they must succeed against any type so that
    # bstr could be used as dict key.
    def __eq__(a, b):
        try:
            b = _pyb_coerce(b)
        except TypeError:
            return False
        return bytes.__eq__(a, b)
    def __ne__(a, b):   return not a.__eq__(b)
    def __lt__(a, b):   return bytes.__lt__(a, _pyb_coerce(b))
    def __gt__(a, b):   return bytes.__gt__(a, _pyb_coerce(b))
    def __le__(a, b):   return bytes.__le__(a, _pyb_coerce(b))
    def __ge__(a, b):   return bytes.__ge__(a, _pyb_coerce(b))

    # len - no need to override

    # [], [:]
    def __getitem__(self, idx):
        x = bytes.__getitem__(self, idx)
        if type(idx) is slice:
            return pyb(x)
        else:
            # bytes[i] returns 1-character bytestring(py2)  or  int(py3)
            # we always return 1-character bytestring
            if PY_MAJOR_VERSION >= 3:
                return pybbyte(x)
            else:
                return pyb(x)

    # __iter__  - yields unicode characters
    def __iter__(self):
        # TODO iterate without converting self to u
        return pyu(self).__iter__()


# XXX cannot `cdef class` with __new__: https://github.com/cython/cython/issues/799
class pyustr(unicode):
    """ustr is unicode-string.

    It is based on unicode and can automatically convert to/from bytes.
    The conversion never fails and never looses information:

        ustr → bstr → ustr

    is always identity even if bytes data is not valid UTF-8.

    ustr is similar to standard unicode type - iterating and accessing its
    elements by [index] yields unicode characters.

    ustr complements bstr and is meant to be used only in situations when
    random access to string characters is needed. Otherwise bstr is more
    preferable and should be enough 99% of the time.

    Operations in between ustr and bstr/bytes/bytearray / unicode coerce to ustr.
    When the coercion happens, bytes and bytearray, similarly to bstr, are also
    treated as UTF8-encoded strings.

    ustr constructor, similarly to the one in bstr, accepts arbitrary objects
    and stringify them. Please refer to bstr and u documentation for details.

    See also: u, bstr/b.
    """

    # don't allow to set arbitrary attributes.
    # won't be needed after switch to -> `cdef class`
    __slots__ = ()

    def __new__(cls, object='', encoding=None, errors=None):
        # encoding or errors  ->  object must expose buffer interface
        if not (encoding is None and errors is None):
            object = _buffer_decode(object, encoding, errors)

        # _bstringify. Note: it handles bstr/ustr / unicode/bytes/bytearray as documented
        object = _bstringify(object)
        assert isinstance(object, (unicode, bytes)), object
        uobj = _pyu(cls, object)
        assert uobj is not None
        return uobj


    def __bytes__(self):    return pyb(self)
    def __unicode__(self):  return self

    def __str__(self):
        if PY_MAJOR_VERSION >= 3:
            return self
        else:
            return pyb(self)


    # override reduce for protocols < 2. Builtin handler for that goes through
    # copyreg._reduce_ex which eventually calls unicode(ustr-instance) to
    # retrieve state, which gives ustr, not unicode. Fix state to be unicode ourselves.
    def __reduce_ex__(self, protocol):
        if protocol >= 2:
            return unicode.__reduce_ex__(self, protocol)
        return (
            pycopyreg._reconstructor,
            (self.__class__, self.__class__, _udata(self))
        )


    def __hash__(self):
        # see pybstr.__hash__ for why we stick to hash of current str
        if PY_MAJOR_VERSION >= 3:
            return unicode.__hash__(self)
        else:
            return hash(pyb(self))

    # == != < > <= >=
    # NOTE == and != are special: they must succeed against any type so that
    # ustr could be used as dict key.
    def __eq__(a, b):
        try:
            b = _pyu_coerce(b)
        except TypeError:
            return False
        return unicode.__eq__(a, b)
    def __ne__(a, b):   return not a.__eq__(b)
    def __lt__(a, b):   return unicode.__lt__(a, _pyu_coerce(b))
    def __gt__(a, b):   return unicode.__gt__(a, _pyu_coerce(b))
    def __le__(a, b):   return unicode.__le__(a, _pyu_coerce(b))
    def __ge__(a, b):   return unicode.__ge__(a, _pyu_coerce(b))

    # len - no need to override

    # [], [:]
    def __getitem__(self, idx):
        return pyu(unicode.__getitem__(self, idx))

    # __iter__
    def __iter__(self):
        if PY_MAJOR_VERSION >= 3:
            return _pyustrIter(unicode.__iter__(self))
        else:
            # on python 2 unicode does not have .__iter__
            return PySeqIter_New(self)


# _pyustrIter wraps unicode iterator to return pyustr for each yielded character.
cdef class _pyustrIter:
    cdef object uiter
    def __init__(self, uiter):
        self.uiter = uiter
    def __iter__(self):
        return self
    def __next__(self):
        x = next(self.uiter)
        return pyu(x)


# _bdata/_udata retrieve raw data from bytes/unicode.
def _bdata(obj): # -> bytes
    assert isinstance(obj, bytes)
    _ = obj.__getnewargs__()[0] # (`bytes-data`,)
    assert type(_) is bytes
    return _
    """
    bcopy = bytes(memoryview(obj))
    assert type(bcopy) is bytes
    return bcopy
    """
def _udata(obj): # -> unicode
    assert isinstance(obj, unicode)
    _ = obj.__getnewargs__()[0] # (`unicode-data`,)
    assert type(_) is unicode
    return _
    """
    cdef Py_UNICODE* u     = PyUnicode_AsUnicode(obj)
    cdef Py_ssize_t  size  = PyUnicode_GetSize(obj)
    cdef unicode     ucopy = PyUnicode_FromUnicode(u, size)
    assert type(ucopy) is unicode
    return ucopy
    """


# initialize .tp_print for pybstr so that this type could be printed.
# If we don't - printing it will result in `RuntimeError: print recursion`
# because str of this type never reaches real bytes or unicode.
# Do it only on python2, because python3 does not use tp_print at all.
# NOTE pyustr does not need this because on py2 str(pyustr) returns pybstr.
IF PY2:
    # NOTE Cython does not define tp_print for PyTypeObject - do it ourselves
    from libc.stdio cimport FILE
    cdef extern from "Python.h":
        ctypedef int (*printfunc)(PyObject *, FILE *, int) except -1
        ctypedef struct _PyTypeObject_Print "PyTypeObject":
            printfunc tp_print

    cdef int _pybstr_tp_print(PyObject *obj, FILE *f, int nesting) except -1:
        o = <bytes>obj
        o = bytes(buffer(o))  # change tp_type to bytes instead of pybstr
        return (<_PyTypeObject_Print*>Py_TYPE(o)) .tp_print(<PyObject*>o, f, nesting)

    (<_PyTypeObject_Print*>Py_TYPE(pybstr())) .tp_print = _pybstr_tp_print


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
        qobj = pyu(qobj)
    else:
        qobj = pyb(qobj)

    return qobj



# ---- _bstringify ----

# _bstringify returns string representation of obj.
# it is similar to unicode(obj).
cdef _bstringify(object obj): # -> unicode|bytes
    if type(obj) in (pybstr, pyustr, bytes, unicode):
        return obj
    if type(obj) is bytearray:
        return bytes(obj)

    if PY_MAJOR_VERSION >= 3:
        return unicode(obj)

    else:
        # on py2 mimic manually what unicode(·) does on py3
        # the reason we do it manually is because if we try just
        # unicode(obj), and obj's __str__ returns UTF-8 bytestring, it will
        # fail with UnicodeDecodeError. Similarly if we unconditionally do
        # str(obj), it will fail if obj's __str__ returns unicode.
        if hasattr(obj, '__unicode__'):
            return obj.__unicode__()
        elif hasattr(obj, '__str__'):
            # (u'β').__str__() gives UnicodeEncodeError, but unicode has no
            # .__unicode__ method. Work it around to handle custom unicode
            # subclasses that do not override __str__.
            if type(obj).__str__ is unicode.__str__:
                return unicode(obj)
            return obj.__str__()
        else:
            return repr(obj)


# py2: adjust unicode.tp_richcompare(a,b) to return NotImplemented if b is bstr.
# This way we avoid `UnicodeWarning: Unicode equal comparison failed to convert
# both arguments to Unicode - interpreting them as being unequal`, and that
# further `a == b` returns False even if `b == a` gives True.
#
# NOTE there is no need to do the same for ustr, because ustr inherits from
# unicode and can be always natively converted to unicode by python itself.
cdef richcmpfunc _unicode_tp_richcompare = Py_TYPE(u'').tp_richcompare

cdef object _unicode_tp_xrichcompare(object a, object b, int op):
    if isinstance(b, pybstr):
        return NotImplemented
    return _unicode_tp_richcompare(a, b, op)

cdef object _unicode_x__eq__(object a, object b):   return _unicode_tp_richcompare(a, b, Py_EQ)
cdef object _unicode_x__ne__(object a, object b):   return _unicode_tp_richcompare(a, b, Py_NE)
cdef object _unicode_x__lt__(object a, object b):   return _unicode_tp_richcompare(a, b, Py_LT)
cdef object _unicode_x__gt__(object a, object b):   return _unicode_tp_richcompare(a, b, Py_GT)
cdef object _unicode_x__le__(object a, object b):   return _unicode_tp_richcompare(a, b, Py_LE)
cdef object _unicode_x__ge__(object a, object b):   return _unicode_tp_richcompare(a, b, Py_GE)

if PY_MAJOR_VERSION < 3:
    def _():
        cdef PyTypeObject* t
        for pyt in [unicode] + unicode.__subclasses__():
            assert isinstance(pyt, type)
            t = <PyTypeObject*>pyt
            if t.tp_richcompare == _unicode_tp_richcompare:
                t.tp_richcompare = _unicode_tp_xrichcompare
                _patch_slot(t, "__eq__", _unicode_x__eq__)
                _patch_slot(t, "__ne__", _unicode_x__ne__)
                _patch_slot(t, "__lt__", _unicode_x__lt__)
                _patch_slot(t, "__gt__", _unicode_x__gt__)
                _patch_slot(t, "__le__", _unicode_x__le__)
                _patch_slot(t, "__ge__", _unicode_x__ge__)
    _()


# patch:
#
# - bytearray.__init__ to accept ustr instead of raising 'TypeError:
#   string argument without an encoding'  (pybug: bytearray() should respect
#   __bytes__ similarly to bytes)
cdef initproc   _bytearray_tp_init    = (<_XPyTypeObject*>bytearray) .tp_init

cdef int _bytearray_tp_xinit(object self, PyObject* args, PyObject* kw) except -1:
    if args != NULL  and  (kw == NULL  or  (not <object>kw)):
        argv = <object>args
        if isinstance(argv, tuple)  and  len(argv) == 1:
            arg = argv[0]
            if isinstance(arg, pyustr):
                argv = (pyb(arg),)      # NOTE argv is kept alive till end of function
                args = <PyObject*>argv  #      no need to incref it
    return _bytearray_tp_init(self, args, kw)


def _bytearray_x__init__(self, *argv, **kw):
    # NOTE don't return - just call: __init__ should return None
    _bytearray_tp_xinit(self, <PyObject*>argv, <PyObject*>kw)

def _():
    cdef PyTypeObject* t
    for pyt in [bytearray] + bytearray.__subclasses__():
        assert isinstance(pyt, type)
        t = <PyTypeObject*>pyt
        t_ = <_XPyTypeObject*>t
        if t_.tp_init == _bytearray_tp_init:
            t_.tp_init = _bytearray_tp_xinit
            _patch_slot(t, '__init__', _bytearray_x__init__)
_()

# _patch_slot installs func_or_descr into typ's __dict__ as name.
#
# if func_or_descr is descriptor (has __get__), it is installed as is.
# otherwise it is wrapped with "unbound method" descriptor.
cdef _patch_slot(PyTypeObject* typ, str name, object func_or_descr):
    typdict = <dict>(typ.tp_dict)
    #print("\npatching %s.%s  with  %r" % (typ.tp_name, name, func_or_descr))
    #print("old:  %r" % typdict.get(name))

    if hasattr(func_or_descr, '__get__'):
        descr = func_or_descr
    else:
        func = func_or_descr
        if PY_MAJOR_VERSION < 3:
            descr = pytypes.MethodType(func, None, <object>typ)
        else:
            descr = _UnboundMethod(func)

    typdict[name] = descr
    #print("new:  %r" % typdict.get(name))
    PyType_Modified(typ)


cdef class _UnboundMethod(object): # they removed unbound methods on py3
    cdef object func
    def __init__(self, func):
        self.func = func
    def __get__(self, obj, objtype):
        return pyfunctools.partial(self.func, obj)


# ---- misc ----

# _buffer_py2 returns buffer(obj) on py2 / fails on py3
cdef object _buffer_py2(object obj):
    IF PY2:                 # cannot `if PY_MAJOR_VERSION < 3` because then cython errors
        return buffer(obj)  # "undeclared name not builtin: buffer"
    ELSE:
        raise AssertionError("must be called only on py2")

# _buffer_decode decodes buf to unicode according to encoding and errors.
#
# buf must expose buffer interface.
# encoding/errors can be None meaning to use default utf-8/strict.
cdef unicode _buffer_decode(buf, encoding, errors):
    if encoding is None: encoding = 'utf-8' # NOTE always UTF-8, not sys.getdefaultencoding
    if errors   is None: errors   = 'strict'
    if _XPyObject_CheckOldBuffer(buf):
        buf = _buffer_py2(buf)
    else:
        buf = memoryview(buf)
    return bytearray(buf).decode(encoding, errors)

cdef extern from "Python.h":
    """
    static int _XPyObject_CheckOldBuffer(PyObject *o) {
    #if PY_MAJOR_VERSION >= 3
        // no old-style buffers on py3
        return 0;
    #else
        return PyObject_CheckReadBuffer(o);
    #endif
    }
    """
    bint _XPyObject_CheckOldBuffer(object o)


# ---- UTF-8 encode/decode ----

from six import unichr                      # py2: unichr       py3: chr
from six import int2byte as bchr            # py2: chr          py3: lambda x: bytes((x,))

cdef int _rune_error = 0xFFFD # unicode replacement character
_py_rune_error = _rune_error

cdef bint _ucs2_build = (sys.maxunicode ==     0xffff)      #    ucs2
assert    _ucs2_build or sys.maxunicode >= 0x0010ffff       # or ucs4

# _utf8_decode_rune decodes next UTF8-character from byte string s.
#
# _utf8_decode_rune(s) -> (r, size)
def _py_utf8_decode_rune(const uint8_t[::1] s):
    return _utf8_decode_rune(s)
cdef (int, int) _utf8_decode_rune(const uint8_t[::1] s):
    if len(s) == 0:
        return _rune_error, 0

    cdef int l = min(len(s), 4)  # max size of an UTF-8 encoded character
    while l > 0:
        try:
            r = PyUnicode_DecodeUTF8(<char*>&s[0], l, 'strict')
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
def _utf8_decode_surrogateescape(const uint8_t[::1] s): # -> unicode
    if PY_MAJOR_VERSION >= 3:
        if len(s) == 0:
            return u''  # avoid out-of-bounds slice access on &s[0]
        else:
            return PyUnicode_DecodeUTF8(<char*>&s[0], len(s), 'surrogateescape')

    # py2 does not have surrogateescape error handler, and even if we
    # provide one, builtin bytes.decode() does not treat surrogate
    # sequences as error. -> Do the decoding ourselves.
    outv = []
    emit = outv.append

    while len(s) > 0:
        r, width = _utf8_decode_rune(s)
        if r == _rune_error  and  width == 1:
            b = s[0]
            assert 0x80 <= b <= 0xff, b
            emit(unichr(0xdc00 + b))

        # python2 "correctly" decodes surrogates - don't allow that as
        # surrogates are not valid UTF-8:
        # https://github.com/python/cpython/blob/v3.8.1-118-gdbb37aac142/Objects/stringlib/codecs.h#L153-L157
        # (python3 raises UnicodeDecodeError for surrogates)
        elif 0xd800 <= r < 0xdfff:
            for c in s[:width]:
                if c >= 0x80:
                    emit(unichr(0xdc00 + c))
                else:
                    emit(unichr(c))

        else:
            emit(_xunichr(r))

        s = s[width:]

    return u''.join(outv)


# _utf8_encode_surrogateescape mimics s.encode('utf-8', 'surrogateescape') from py3.
def _utf8_encode_surrogateescape(s): # -> bytes
    assert isinstance(s, unicode)
    if PY_MAJOR_VERSION >= 3:
        return unicode.encode(s, 'UTF-8', 'surrogateescape')

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
