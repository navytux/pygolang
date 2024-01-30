# -*- coding: utf-8 -*-
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
"""_golang_str.pyx complements _golang.pyx and keeps everything related to strings.

It is included from _golang.pyx .
"""

from libc.stdio cimport fprintf, stderr # XXX kill

from golang.unicode cimport utf8

from cpython cimport PyUnicode_AsUnicode, PyUnicode_GetSize, PyUnicode_FromUnicode
from cpython cimport PyUnicode_DecodeUTF8
from cpython cimport PyTypeObject, Py_TYPE, reprfunc, richcmpfunc, binaryfunc
from cpython cimport Py_EQ, Py_NE, Py_LT, Py_GT, Py_LE, Py_GE
from cpython.iterobject cimport PySeqIter_New
from cpython cimport PyThreadState_GetDict, PyDict_SetItem
from cpython cimport PyObject_CheckBuffer
from cpython cimport Py_TPFLAGS_HAVE_GC, Py_TPFLAGS_HEAPTYPE, Py_TPFLAGS_READY, PyType_Ready
from cpython cimport PyBytes_Format, PyUnicode_Format, PyObject_Str

cdef extern from "Python.h":
    PyTypeObject PyBytes_Type
    ctypedef struct PyBytesObject:
        char *ob_sval

cdef extern from "Python.h":
    PyTypeObject PyUnicode_Type
    ctypedef struct PyUnicodeObject:
        pass

cdef extern from "Python.h":
    """
    #if PY_MAJOR_VERSION < 3
    // on py2, PyDict_GetItemWithError is called _PyDict_GetItemWithError
    // NOTE Cython3 provides PyDict_GetItemWithError out of the box
    # define PyDict_GetItemWithError _PyDict_GetItemWithError
    #endif
    """
    PyObject* PyDict_GetItemWithError(object, object) except? NULL  # borrowed ref

    Py_ssize_t PY_SSIZE_T_MAX
    void PyType_Modified(PyTypeObject *)

cdef extern from "Python.h":
    ctypedef int (*initproc)(object, PyObject *, PyObject *) except -1
    ctypedef struct _XPyTypeObject "PyTypeObject":
        PyObject* tp_new(PyTypeObject*, PyObject*, PyObject*) except NULL
        initproc  tp_init

        Py_ssize_t tp_vectorcall_offset
        Py_ssize_t tp_weaklistoffset

        PyObject *tp_bases
        PyObject *tp_mro
        PyObject *tp_cache
        PyObject *tp_weaklist
        PyObject *tp_subclasses

        PySequenceMethods *tp_as_sequence
        PyMethodDef       *tp_methods
        PyMemberDef       *tp_members

    ctypedef struct PySequenceMethods:
        binaryfunc sq_concat
        binaryfunc sq_inplace_concat
        object (*sq_slice) (object, Py_ssize_t, Py_ssize_t)     # present only on py2

cdef extern from "Python.h":
    ctypedef struct PyVarObject:
        Py_ssize_t ob_size


cdef extern from "funchook.h" nogil:
    ctypedef struct funchook_t
    funchook_t* funchook_create()
    int funchook_prepare(funchook_t* h, void** target_func, void* hook_func)
    int funchook_install(funchook_t* h, int flags)
    int funchook_uninstall(funchook_t* h, int flags)
    int funchook_destroy(funchook_t*)
    const char* funchook_error_message(const funchook_t*)
    int funchook_set_debug_file(const char* name)


from cython cimport no_gc

from libc.stdio cimport FILE

from golang cimport strconv
import string as pystring
import types as pytypes
import functools as pyfunctools
import re as pyre


# zbytes/zunicode point to original std bytes/unicode types even if they will be patched.
# we use them to invoke original bytes/unicode methods.
cdef object zbytes   = <object>(&PyBytes_Type)
cdef object zunicode = <object>(&PyUnicode_Type)

# pybstr/pyustr point to version of bstr/ustr types that is actually in use:
# - when bytes/unicode are not patched -> to _pybstr/_pyustr
# - when bytes/unicode will be patched -> to bytes/unicode to where original
#   _pybstr/_pyustr were copied during bytes/unicode patching.
# at runtime the code should use pybstr/pyustr instead of _pybstr/_pyustr.
pybstr = _pybstr    # initially point to -> _pybstr/_pyustr
pyustr = _pyustr    # TODO -> cdef for speed


cpdef pyb(s): # -> bstr
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

cpdef pyu(s): # -> ustr
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
    # like  zbytes.__new__(bcls, s)  but call zbytes.tp_new directly
    # else tp_new_wrapper complains because pybstr.tp_new != zbytes.tp_new
    argv = (s,)
    obj = <object>(<_XPyTypeObject*>zbytes).tp_new(<PyTypeObject*>bcls, <PyObject*>argv, NULL)
    Py_DECREF(obj)
    return obj

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
    # like  zunicode .__new__(bcls, s)  but call zunicode.tp_new directly
    # else tp_new_wrapper complains because pyustr.tp_new != zunicode.tp_new
    argv = (s,)
    obj = <object>(<_XPyTypeObject*>zunicode).tp_new(<PyTypeObject*>ucls, <PyObject*>argv, NULL)
    Py_DECREF(obj)
    return obj

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

# _pybu_rcoerce coerces x from `x op b|u` to either bstr or ustr.
# NOTE bytearray is handled outside of this function.
cdef _pybu_rcoerce(x): # -> bstr|ustr
    if isinstance(x, bytes):
        return pyb(x)
    elif isinstance(x, unicode):
        return pyu(x)
    else:
        raise TypeError('b/u: coerce: invalid type %s' % type(x))


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


# XXX -> bchr ?  (not good as "character" means "unicode character")
#     -> bstr.chr ?
def pybbyte(int i): # -> 1-byte bstr
    """bbyte(i) returns 1-byte bstr with ordinal i."""
    return pyb(bytearray([i]))

def pyuchr(int i):  # -> 1-character ustr
    """uchr(i) returns 1-character ustr with unicode ordinal i."""
    return pyu(unichr(i))


# XXX due to "cannot `cdef class` with __new__" (https://github.com/cython/cython/issues/799)                   XXX review text
# _pybstr.__new__ is hand-made in _pybstr_tp_new which invokes ↓ ._pybstr__new__() .
# we keep it out of class instead of cdef @staticmethod due to https://github.com/cython/cython/issues/5337
# XXX def instead of cdef due to ""Non-trivial keyword arguments and starred arguments not allowed in cdef functions
def _pybstr__new__(cls, object='', encoding=None, errors=None):
    # encoding or errors  ->  object must expose buffer interface
    if not (encoding is None and errors is None):
        object = _buffer_decode(object, encoding, errors)

    # _bstringify. Note: it handles bstr/ustr / unicode/bytes/bytearray as documented
    object = _bstringify(object)
    assert isinstance(object, (unicode, bytes)), object
    bobj = _pyb(cls, object)
    assert bobj is not None
    return bobj

@no_gc                       # note setup.py assist this to compile despite
cdef class _pybstr(bytes):   # https://github.com/cython/cython/issues/711
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

    # XXX due to "cannot `cdef class` with __new__" (https://github.com/cython/cython/issues/799)
    # _pybstr.__new__ is hand-made in _pybstr_tp_new which invokes ↑ _pybstr__new__() .


    def __bytes__(self):    return pyb(self)  # see __str__
    def __unicode__(self):  return pyu(self)

    def __str__(self):
        if PY_MAJOR_VERSION >= 3:
            return pyu(self)
        else:
            return pyb(self)  # self  or  pybstr if it was subclass

    def __repr__(self):
        qself, nonascii_escape = _bpysmartquote_u3b2(self)
        bs = _inbstringify_get()
        if bs.inbstringify == 0  or  bs.inrepr:
            if pybstr is bytes:     # don't wrap with b(...) when bstr replaces builtin str
                if PY_MAJOR_VERSION >= 3:
                    qself = 'b' + qself
                return qself
            if nonascii_escape:         # so that e.g. b(u'\x80') is represented as
                qself = 'b' + qself     # b(b'\xc2\x80'),  not as b('\xc2\x80')
            return "b(" + qself + ")"
        else:
            # [b('β')] goes as ['β'] when under _bstringify for %s
            return qself

    def __reduce_ex__(self, protocol):
        return _bstr__reduce_ex__(self, protocol)

    def __hash__(self):
        # hash of the same unicode and UTF-8 encoded bytes is generally different
        # -> we can't make hash(bstr) == both hash(bytes) and hash(unicode) at the same time.
        # -> make hash(bstr) == hash(str type of current python) so that bstr
        #    could be used as keys in dictionary interchangeably with native str type.
        if PY_MAJOR_VERSION >= 3:
            return hash(pyu(self))
        else:
            return zbytes.__hash__(self)

    # == != < > <= >=
    # NOTE == and != are special: they must succeed against any type so that
    # bstr could be used as dict key.
    def __eq__(a, b):
        try:
            b = _pyb_coerce(b)
        except TypeError:
            return False
        return zbytes.__eq__(a, b)
    def __ne__(a, b):   return not a.__eq__(b)
    def __lt__(a, b):   return zbytes.__lt__(a, _pyb_coerce(b))
    def __gt__(a, b):   return zbytes.__gt__(a, _pyb_coerce(b))
    def __le__(a, b):   return zbytes.__le__(a, _pyb_coerce(b))
    def __ge__(a, b):   return zbytes.__ge__(a, _pyb_coerce(b))

    # len - no need to override

    # [], [:]
    def __getitem__(self, idx):
        x = zbytes.__getitem__(self, idx)
        if type(idx) is slice:
            return pyb(x)
        else:
            # bytes[i] returns 1-character bytestring(py2)  or  int(py3)
            # we always return 1-character bytestring
            if PY_MAJOR_VERSION >= 3:
                return pybbyte(x)
            else:
                return pyb(x)

    # XXX temp disabled
    # __iter__  - yields unicode characters
    def __iter__(self):
        # TODO iterate without converting self to u
        return pyu(self).__iter__()


    # __contains__
    def __contains__(self, key):
        # NOTE on py3 bytes.__contains__ accepts numbers and buffers. We don't want to
        # automatically coerce any of them to bytestrings
        return zbytes.__contains__(self, _pyb_coerce(key))


    # __add__, __radd__     (no need to override __iadd__)
    def __add__(a, b):
        # NOTE Cython < 3 does not automatically support __radd__ for cdef class
        # https://cython.readthedocs.io/en/latest/src/userguide/migrating_to_cy30.html#arithmetic-special-methods
        # see also https://github.com/cython/cython/issues/4750
        if type(a) is not pybstr:
            assert type(b) is pybstr
            return b.__radd__(a)
        return pyb(zbytes.__add__(a, _pyb_coerce(b)))

    def __radd__(b, a):
        # a.__add__(b) returned NotImplementedError, e.g. for unicode.__add__(bstr)
        # u''  + b() -> u()     ; same as u() + b() -> u()
        # b''  + b() -> b()     ; same as b() + b() -> b()
        # barr + b() -> barr
        if isinstance(a, bytearray):
            # force `bytearray +=` to go via bytearray.sq_inplace_concat - see PyNumber_InPlaceAdd
            return NotImplemented
        a = _pybu_rcoerce(a)
        return a.__add__(b)

    # __mul__, __rmul__     (no need to override __imul__)
    def __mul__(a, b):
        if type(a) is not pybstr:
            assert type(b) is pybstr
            return b.__rmul__(a)
        return pyb(zbytes.__mul__(a, b))
    def __rmul__(b, a):
        return b.__mul__(a)


    # %-formatting
    def __mod__(a, b):
        return _bprintf(a, b)
    def __rmod__(b, a):
        # ("..." % x)  calls  "x.__rmod__()" for string subtypes
        # determine output type as in __radd__
        if isinstance(a, bytearray):
            # on py2 bytearray does not implement %
            return NotImplemented   # no need to check for py3 - there our __rmod__ is not invoked
        a = _pybu_rcoerce(a)
        return a.__mod__(b)

    # format
    def format(self, *args, **kwargs):  return pyb(pyu(self).format(*args, **kwargs))
    def format_map(self, mapping):      return pyb(pyu(self).format_map(mapping))
    def __format__(self, format_spec):
        # NOTE don't convert to b due to "TypeError: __format__ must return a str, not pybstr"
        #      we are ok to return ustr even for format(bstr, ...) because in
        #      practice format builtin is never used and it is only s.format()
        #      that is used in programs. This way __format__ will be invoked
        #      only internally.
        #
        # NOTE we are ok to use ustr.__format__ because the only format code
        #      supported by bstr/ustr/unicode __format__ is 's', not e.g. 'r'.
        return pyu(self).__format__(format_spec)


    # encode/decode
    def decode(self, encoding=None, errors=None):
        if encoding is None and errors is None:
            encoding = 'utf-8'             # NOTE always UTF-8, not sys.getdefaultencoding
            errors   = 'surrogateescape'
        else:
            if encoding is None:  encoding = 'utf-8'
            if errors   is None:  errors   = 'strict'

        if encoding == 'utf-8'  and  errors == 'surrogateescape':
            x = _utf8_decode_surrogateescape(self)
        else:
            x = zbytes.decode(self, encoding, errors)
        # on py2 e.g. bytes.decode('string-escape') returns bytes
        if PY_MAJOR_VERSION < 3  and  isinstance(x, bytes):
            return pyb(x)
        return pyu(x)

    if PY_MAJOR_VERSION < 3:
        # whiteout encode inherited from bytes
        # TODO ideally whiteout it in such a way that bstr.encode also raises AttributeError
        encode = property(doc='bstr has no encode')


    # all other string methods

    def capitalize(self):                       return pyb(pyu(self).capitalize())
    def casefold(self):                         return pyb(pyu(self).casefold())
    def center(self, width, fillchar=' '):      return pyb(pyu(self).center(width, fillchar))

    def count(self, sub, start=None, end=None): return zbytes.count(self, _pyb_coerce(sub), start, end)

    def endswith(self, suffix, start=None, end=None):
        if isinstance(suffix, tuple):
            for _ in suffix:
                if self.endswith(_pyb_coerce(_), start, end):
                    return True
            return False
        if start is None: start = 0
        if end   is None: end   = PY_SSIZE_T_MAX
        return zbytes.endswith(self, _pyb_coerce(suffix), start, end)

    def expandtabs(self, tabsize=8):            return pyb(pyu(self).expandtabs(tabsize))

    # NOTE find/index & friends should return byte-position, not unicode-position
    def find(self, sub, start=None, end=None):  return zbytes.find(self, _pyb_coerce(sub), start, end)
    def index(self, sub, start=None, end=None): return zbytes.index(self, _pyb_coerce(sub), start, end)

    def isalnum(self):      return pyu(self).isalnum()
    def isalpha(self):      return pyu(self).isalpha()
    # isascii(self)         no need to override
    def isdecimal(self):    return pyu(self).isdecimal()
    def isdigit(self):      return pyu(self).isdigit()
    def isidentifier(self): return pyu(self).isidentifier()
    def islower(self):      return pyu(self).islower()
    def isnumeric(self):    return pyu(self).isnumeric()
    def isprintable(self):  return pyu(self).isprintable()
    def isspace(self):      return pyu(self).isspace()
    def istitle(self):      return pyu(self).istitle()

    def join(self, iterable):               return pyb(zbytes.join(self, (_pyb_coerce(_) for _ in iterable)))
    def ljust(self, width, fillchar=' '):   return pyb(pyu(self).ljust(width, fillchar))
    def lower(self):                        return pyb(pyu(self).lower())
    def lstrip(self, chars=None):           return pyb(pyu(self).lstrip(chars))
    def partition(self, sep):               return tuple(pyb(_) for _ in zbytes.partition(self, _pyb_coerce(sep)))
    def removeprefix(self, prefix):         return pyb(pyu(self).removeprefix(prefix))
    def removesuffix(self, suffix):         return pyb(pyu(self).removesuffix(suffix))
    def replace(self, old, new, count=-1):  return pyb(zbytes.replace(self, _pyb_coerce(old), _pyb_coerce(new), count))

    # NOTE rfind/rindex & friends should return byte-position, not unicode-position
    def rfind(self, sub, start=None, end=None):   return zbytes.rfind(self, _pyb_coerce(sub), start, end)
    def rindex(self, sub, start=None, end=None):  return zbytes.rindex(self, _pyb_coerce(sub), start, end)

    def rjust(self, width, fillchar=' '):   return pyb(pyu(self).rjust(width, fillchar))
    def rpartition(self, sep):              return tuple(pyb(_) for _ in zbytes.rpartition(self, _pyb_coerce(sep)))
    def rsplit(self, sep=None, maxsplit=-1):
        v = pyu(self).rsplit(sep, maxsplit)
        return list([pyb(_) for _ in v])
    def rstrip(self, chars=None):           return pyb(pyu(self).rstrip(chars))
    def split(self, sep=None, maxsplit=-1):
        v = pyu(self).split(sep, maxsplit)
        return list([pyb(_) for _ in v])
    def splitlines(self, keepends=False):   return list(pyb(_) for _ in pyu(self).splitlines(keepends))

    def startswith(self, prefix, start=None, end=None):
        if isinstance(prefix, tuple):
            for _ in prefix:
                if self.startswith(_pyb_coerce(_), start, end):
                    return True
            return False
        if start is None: start = 0
        if end   is None: end   = PY_SSIZE_T_MAX
        return zbytes.startswith(self, _pyb_coerce(prefix), start, end)

    def strip(self, chars=None):            return pyb(pyu(self).strip(chars))
    def swapcase(self):                     return pyb(pyu(self).swapcase())
    def title(self):                        return pyb(pyu(self).title())
    def translate(self, table, delete=None):
        # bytes mode  (compatibility with str/py2)
        if table is None  or isinstance(table, zbytes)  or  delete is not None:
            if delete is None:  delete = b''
            return pyb(zbytes.translate(self, table, delete))
        # unicode mode
        else:
            return pyb(pyu(self).translate(table))

    def upper(self):                        return pyb(pyu(self).upper())
    def zfill(self, width):                 return pyb(pyu(self).zfill(width))

    @staticmethod
    def maketrans(x=None, y=None, z=None):
        return pyustr.maketrans(x, y, z)


# hand-made _pybstr.__new__  (workaround for https://github.com/cython/cython/issues/799)
cdef PyObject* _pybstr_tp_new(PyTypeObject* _cls, PyObject* _argv, PyObject* _kw) except NULL:
    argv = ()
    if _argv != NULL:
        argv = <object>_argv
    kw = {}
    if _kw != NULL:
        kw = <object>_kw

    cdef object x = _pybstr__new__(<object>_cls, *argv, **kw)
    Py_INCREF(x)
    return <PyObject*>x
(<_XPyTypeObject*>_pybstr).tp_new   = &_pybstr_tp_new

# bytes uses "optimized" and custom .tp_basicsize and .tp_itemsize:
# https://github.com/python/cpython/blob/v2.7.18-0-g8d21aa21f2c/Objects/stringobject.c#L26-L32
# https://github.com/python/cpython/blob/v2.7.18-0-g8d21aa21f2c/Objects/stringobject.c#L3816-L3820
(<PyTypeObject*>_pybstr) .tp_basicsize  =  (<PyTypeObject*>zbytes).tp_basicsize
(<PyTypeObject*>_pybstr) .tp_itemsize   =  (<PyTypeObject*>zbytes).tp_itemsize

# make sure _pybstr C layout corresponds to bytes C layout exactly
# we patched cython to allow from-bytes cdef class inheritance and we also set
# .tp_basicsize directly above. All this works ok only if C layouts for _pybstr
# and bytes are completely the same.
assert sizeof(_pybstr) == sizeof(PyBytesObject)

# XXX text
def _pyustr__new__(cls, object='', encoding=None, errors=None):
    # encoding or errors  ->  object must expose buffer interface
    if not (encoding is None and errors is None):
        object = _buffer_decode(object, encoding, errors)

    # _bstringify. Note: it handles bstr/ustr / unicode/bytes/bytearray as documented
    object = _bstringify(object)
    assert isinstance(object, (unicode, bytes)), object
    uobj = _pyu(cls, object)
    assert uobj is not None
    return uobj

@no_gc
cdef class _pyustr(unicode):
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

    # XXX due to "cannot `cdef class` with __new__" (https://github.com/cython/cython/issues/799)
    # _pyustr.__new__ is hand-made in _pyustr_tp_new which invokes ↑ _pyustr__new__() .


    def __bytes__(self):    return pyb(self)
    def __unicode__(self):  return pyu(self)  # see __str__

    def __str__(self):
        if PY_MAJOR_VERSION >= 3:
            return pyu(self)  # = self  or  pyustr if it was subclass
        else:
            return pyb(self)

    def __repr__(self):
        qself, nonascii_escape = _upysmartquote_u3b2(self)
        bs = _inbstringify_get()
        if bs.inbstringify == 0  or  bs.inrepr:
            if pyustr is unicode:   # don't wrap with u(...) when ustr replaces builtin str/unicode
                if not nonascii_escape: # but only if the string is valid utf-8
                    if PY_MAJOR_VERSION < 3:
                        qself = 'u'+qself
                    return qself
            if nonascii_escape:
                qself = 'b'+qself       # see bstr.__repr__
            return "u(" + qself + ")"
        else:
            # [u('β')] goes as ['β'] when under _bstringify for %s
            return qself

    def __reduce_ex__(self, protocol):
        return _ustr__reduce_ex__(self, protocol)

    def __hash__(self):
        # see _pybstr.__hash__ for why we stick to hash of current str
        if PY_MAJOR_VERSION >= 3:
            return zunicode.__hash__(self)
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
        return zunicode.__eq__(a, b)
    def __ne__(a, b):   return not a.__eq__(b)
    def __lt__(a, b):   return zunicode.__lt__(a, _pyu_coerce(b))
    def __gt__(a, b):   return zunicode.__gt__(a, _pyu_coerce(b))
    def __le__(a, b):   return zunicode.__le__(a, _pyu_coerce(b))
    def __ge__(a, b):   return zunicode.__ge__(a, _pyu_coerce(b))

    # len - no need to override

    # [], [:]
    def __getitem__(self, idx):
        return pyu(zunicode.__getitem__(self, idx))

    # __iter__
    def __iter__(self):
        if PY_MAJOR_VERSION >= 3:
            return _pyustrIter(zunicode.__iter__(self))
        else:
            # on python 2 unicode does not have .__iter__
            return PySeqIter_New(self)


    # __contains__
    def __contains__(self, key):
        return zunicode.__contains__(self, _pyu_coerce(key))


    # __add__, __radd__     (no need to override __iadd__)
    def __add__(a, b):
        # NOTE Cython < 3 does not automatically support __radd__ for cdef class
        # https://cython.readthedocs.io/en/latest/src/userguide/migrating_to_cy30.html#arithmetic-special-methods
        # see also https://github.com/cython/cython/issues/4750
        if type(a) is not pyustr:
            assert type(b) is pyustr,  type(b)
            return b.__radd__(a)
        return pyu(zunicode.__add__(a, _pyu_coerce(b)))

    def __radd__(b, a):
        # a.__add__(b) returned NotImplementedError, e.g. for unicode.__add__(bstr)
        # u''  + u() -> u()     ; same as u() + u() -> u()
        # b''  + u() -> b()     ; same as b() + u() -> b()
        # barr + u() -> barr
        if isinstance(a, bytearray):
            # force `bytearray +=` to go via bytearray.sq_inplace_concat - see PyNumber_InPlaceAdd
            # for pyustr this relies on patch to bytearray.sq_inplace_concat to accept ustr as bstr
            return  NotImplemented
        a = _pybu_rcoerce(a)
        return a.__add__(b)


    # __mul__, __rmul__     (no need to override __imul__)
    def __mul__(a, b):
        if type(a) is not pyustr:
            assert type(b) is pyustr,  type(b)
            return b.__rmul__(a)
        return pyu(zunicode.__mul__(a, b))
    def __rmul__(b, a):
        return b.__mul__(a)


    # %-formatting
    def __mod__(a, b):
        return pyu(pyb(a).__mod__(b))
    def __rmod__(b, a):
        # ("..." % x)  calls  "x.__rmod__()" for string subtypes
        # determine output type as in __radd__
        if isinstance(a, bytearray):
            return NotImplemented   # see bstr.__rmod__
        a = _pybu_rcoerce(a)
        return a.__mod__(b)

    # format
    def format(self, *args, **kwargs):
        return pyu(_bvformat(self, args, kwargs))
    def format_map(self, mapping):
        return pyu(_bvformat(self, (), mapping))
    def __format__(self, format_spec):
        # NOTE not e.g. `_bvformat(_pyu_coerce(format_spec), (self,))` because
        #      the only format code that string.__format__ should support is
        #      's', not e.g. 'r'.
        return pyu(zunicode.__format__(self, format_spec))


    # encode/decode
    def encode(self, encoding=None, errors=None):
        if encoding is None and errors is None:
            encoding = 'utf-8'             # NOTE always UTF-8, not sys.getdefaultencoding
            errors   = 'surrogateescape'
        else:
            if encoding is None:  encoding = 'utf-8'
            if errors   is None:  errors   = 'strict'

        if encoding == 'utf-8'  and  errors == 'surrogateescape':
            x = _utf8_encode_surrogateescape(self)
        else:
            x = zunicode.encode(self, encoding, errors)
        return pyb(x)

    if PY_MAJOR_VERSION < 3:
        # whiteout decode inherited from unicode
        # TODO ideally whiteout it in such a way that ustr.decode also raises AttributeError
        decode = property(doc='ustr has no decode')


    # all other string methods

    def capitalize(self):   return pyu(zunicode.capitalize(self))
    def casefold(self):     return pyu(zunicode.casefold(self))
    def center(self, width, fillchar=' '):      return pyu(zunicode.center(self, width, _pyu_coerce(fillchar)))
    def count(self, sub, start=None, end=None):
        # cython optimizes unicode.count to directly call PyUnicode_Count -
        # - cannot use None for start/stop  https://github.com/cython/cython/issues/4737
        if start is None: start = 0
        if end   is None: end   = PY_SSIZE_T_MAX
        return zunicode.count(self, _pyu_coerce(sub), start, end)
    def endswith(self, suffix, start=None, end=None):
        if isinstance(suffix, tuple):
            for _ in suffix:
                if self.endswith(_pyu_coerce(_), start, end):
                    return True
            return False
        if start is None: start = 0
        if end   is None: end   = PY_SSIZE_T_MAX
        return zunicode.endswith(self, _pyu_coerce(suffix), start, end)
    def expandtabs(self, tabsize=8):            return pyu(zunicode.expandtabs(self, tabsize))
    def find(self, sub, start=None, end=None):
        if start is None: start = 0
        if end   is None: end   = PY_SSIZE_T_MAX
        return zunicode.find(self, _pyu_coerce(sub), start, end)
    def index(self, sub, start=None, end=None):
        if start is None: start = 0
        if end   is None: end   = PY_SSIZE_T_MAX
        return zunicode.index(self, _pyu_coerce(sub), start, end)

    # isalnum(self)         no need to override
    # isalpha(self)         no need to override
    # isascii(self)         no need to override
    # isdecimal(self)       no need to override
    # isdigit(self)         no need to override
    # isidentifier(self)    no need to override
    # islower(self)         no need to override
    # isnumeric(self)       no need to override
    # isprintable(self)     no need to override
    # isspace(self)         no need to override
    # istitle(self)         no need to override

    def join(self, iterable):               return pyu(zunicode.join(self, (_pyu_coerce(_) for _ in iterable)))
    def ljust(self, width, fillchar=' '):   return pyu(zunicode.ljust(self, width, _pyu_coerce(fillchar)))
    def lower(self):                        return pyu(zunicode.lower(self))
    def lstrip(self, chars=None):           return pyu(zunicode.lstrip(self, _xpyu_coerce(chars)))
    def partition(self, sep):               return tuple(pyu(_) for _ in zunicode.partition(self, _pyu_coerce(sep)))
    def removeprefix(self, prefix):         return pyu(zunicode.removeprefix(self, _pyu_coerce(prefix)))
    def removesuffix(self, suffix):         return pyu(zunicode.removesuffix(self, _pyu_coerce(suffix)))
    def replace(self, old, new, count=-1):  return pyu(zunicode.replace(self, _pyu_coerce(old), _pyu_coerce(new), count))
    def rfind(self, sub, start=None, end=None):
        if start is None: start = 0
        if end   is None: end   = PY_SSIZE_T_MAX
        return zunicode.rfind(self, _pyu_coerce(sub), start, end)
    def rindex(self, sub, start=None, end=None):
        if start is None: start = 0
        if end   is None: end   = PY_SSIZE_T_MAX
        return zunicode.rindex(self, _pyu_coerce(sub), start, end)
    def rjust(self, width, fillchar=' '):   return pyu(zunicode.rjust(self, width, _pyu_coerce(fillchar)))
    def rpartition(self, sep):              return tuple(pyu(_) for _ in zunicode.rpartition(self, _pyu_coerce(sep)))
    def rsplit(self, sep=None, maxsplit=-1):
        v = zunicode.rsplit(self, _xpyu_coerce(sep), maxsplit)
        return list([pyu(_) for _ in v])
    def rstrip(self, chars=None):           return pyu(zunicode.rstrip(self, _xpyu_coerce(chars)))
    def split(self, sep=None, maxsplit=-1):
        # cython optimizes unicode.split to directly call PyUnicode_Split - cannot use None for sep
        # and cannot also use object=NULL  https://github.com/cython/cython/issues/4737
        if sep is None:
            if PY_MAJOR_VERSION >= 3:
                v = zunicode.split(self, maxsplit=maxsplit)
            else:
                # on py2 unicode.split does not accept keyword arguments
                v = zunicode.split(self, None, maxsplit)
        else:
            v = zunicode.split(self, _pyu_coerce(sep), maxsplit)
        return list([pyu(_) for _ in v])
    def splitlines(self, keepends=False):   return list(pyu(_) for _ in zunicode.splitlines(self, keepends))
    def startswith(self, prefix, start=None, end=None):
        if isinstance(prefix, tuple):
            for _ in prefix:
                if self.startswith(_pyu_coerce(_), start, end):
                    return True
            return False
        if start is None: start = 0
        if end   is None: end   = PY_SSIZE_T_MAX
        return zunicode.startswith(self, _pyu_coerce(prefix), start, end)
    def strip(self, chars=None):            return pyu(zunicode.strip(self, _xpyu_coerce(chars)))
    def swapcase(self):                     return pyu(zunicode.swapcase(self))
    def title(self):                        return pyu(zunicode.title(self))

    def translate(self, table):
        # unicode.translate does not accept bstr values
        t = {}
        for k,v in table.items():
            if not isinstance(v, int):  # either unicode ordinal,
                v = _xpyu_coerce(v)     # character or None
            t[k] = v
        return pyu(zunicode.translate(self, t))

    def upper(self):                        return pyu(zunicode.upper(self))
    def zfill(self, width):                 return pyu(zunicode.zfill(self, width))

    @staticmethod
    def maketrans(x=None, y=None, z=None):
        if PY_MAJOR_VERSION >= 3:
            if y is None:
                # std maketrans(x) accepts only int|unicode keys
                _ = {}
                for k,v in x.items():
                    if not isinstance(k, int):
                        k = pyu(k)
                    _[k] = v
                return zunicode.maketrans(_)
            elif z is None:
                return zunicode.maketrans(pyu(x), pyu(y))  # std maketrans does not accept b
            else:
                return zunicode.maketrans(pyu(x), pyu(y), pyu(z))  # ----//----

        # hand-made on py2
        t = {}
        if y is not None:
            x = pyu(x)
            y = pyu(y)
            if len(x) != len(y):
                raise ValueError("len(x) must be == len(y))")
            for (xi,yi) in zip(x,y):
                t[ord(xi)] = ord(yi)
            if z is not None:
                z = pyu(z)
                for _ in z:
                    t[ord(_)] = None
        else:
            if type(x) is not dict:
                raise TypeError("sole x must be dict")
            for k,v in x.iteritems():
                if not isinstance(k, (int,long)):
                    k = ord(pyu(k))
                t[k] = pyu(v)
        return t


# hand-made _pyustr.__new__  (workaround for https://github.com/cython/cython/issues/799)
cdef PyObject* _pyustr_tp_new(PyTypeObject* _cls, PyObject* _argv, PyObject* _kw) except NULL:
    argv = ()
    if _argv != NULL:
        argv = <object>_argv
    kw = {}
    if _kw != NULL:
        kw = <object>_kw

    cdef object x = _pyustr__new__(<object>_cls, *argv, **kw)
    Py_INCREF(x)
    return <PyObject*>x
(<_XPyTypeObject*>_pyustr).tp_new   = &_pyustr_tp_new

# similarly to bytes - want same C layout for _pyustr vs unicode
assert sizeof(_pyustr) == sizeof(PyUnicodeObject)


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
    if type(obj) is not bytes:
        obj = obj.__getnewargs__()[0] # (`bytes-data`,)
    assert type(obj) is bytes
    return obj
    """
    bcopy = bytes(memoryview(obj))
    assert type(bcopy) is bytes
    return bcopy
    """
def _udata(obj): # -> unicode
    assert isinstance(obj, unicode)
    if type(obj) is not unicode:
        obj = obj.__getnewargs__()[0] # (`unicode-data`,)
    assert type(obj) is unicode
    return obj
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
    # Cython does not define tp_print for PyTypeObject - do it ourselves
    cdef extern from "Python.h":
        ctypedef int (*printfunc)(PyObject *, FILE *, int) except -1
        ctypedef struct _PyTypeObject_Print "PyTypeObject":
            printfunc   tp_print
        int Py_PRINT_RAW

    cdef int _pybstr_tp_print(PyObject *obj, FILE *f, int flags) except -1:
        o = <object>obj
        if flags & Py_PRINT_RAW:
            # emit str of the object instead of repr
            # https://docs.python.org/2.7/c-api/object.html#c.PyObject_Print
            pass
        else:
            # emit repr
            o = repr(o)

        assert isinstance(o, bytes)
        o = <bytes>o
        o = bytes(buffer(o))  # change tp_type to bytes instead of pybstr
        return (<_PyTypeObject_Print*>zbytes) .tp_print(<PyObject*>o, f, Py_PRINT_RAW)

    (<_PyTypeObject_Print*>Py_TYPE(_pybstr())) .tp_print = _pybstr_tp_print


# whiteout .sq_slice for pybstr/pyustr inherited from str/unicode.
# This way slice access always goes through our __getitem__ implementation.
# If we don't do this e.g. bstr[:] will be handled by str.__getslice__ instead
# of bstr.__getitem__, and will return str instead of bstr.
if PY2:
    (<_XPyTypeObject*>_pybstr) .tp_as_sequence.sq_slice = NULL
    (<_XPyTypeObject*>_pyustr) .tp_as_sequence.sq_slice = NULL


# ---- adjust bstr/ustr classes after what cython generated ----

# for pybstr/pyustr cython generates .tp_dealloc that refer to bytes/unicode types directly.
# override that to refer to zbytes/zunicode to avoid infinite recursion on free.
cdef void _pybstr_tp_dealloc(PyObject *self):   (<PyTypeObject*>zbytes)   .tp_dealloc(self)
cdef void _pyustr_tp_dealloc(PyObject *self):   (<PyTypeObject*>zunicode) .tp_dealloc(self)
(<PyTypeObject*>pybstr).tp_dealloc = &_pybstr_tp_dealloc
(<PyTypeObject*>pyustr).tp_dealloc = &_pyustr_tp_dealloc

# change names of bstr/ustr to be e.g. "golang.bstr" instead of "golang._golang._bstr"  XXX adjust after .name=str
# this makes sure that unpickling saved bstr does not load via unpatched origin
# class, and is also generally good for saving pickle size and for reducing _golang exposure.
# XXX -> _golang_str_pickle.pyx ?
(<PyTypeObject*>pybstr).tp_name = "golang.bstr"
(<PyTypeObject*>pyustr).tp_name = "golang.ustr"
assert pybstr.__module__ == "golang";  assert pybstr.__name__ == "bstr"
assert pyustr.__module__ == "golang";  assert pyustr.__name__ == "ustr"

# remove unsupported bstr/ustr methods. do it outside of `cdef class` to
# workaround https://github.com/cython/cython/issues/4556 (`if ...` during
# `cdef class` is silently handled wrongly)
cdef _bstrustr_remove_unsupported_slots():
    vslot = (
        'casefold',     # py3.3     TODO provide py2 implementation
        'isidentifier', # py3       TODO provide fallback implementation
        'isprintable',  # py3       TODO provide fallback implementation
        'removeprefix', # py3.9     TODO provide fallback implementation
        'removesuffix', # py3.9     TODO provide fallback implementation
    )
    for slot in vslot:
        if not hasattr(zunicode, slot):
            if hasattr(pybstr, slot):   # we might have already removed it on previous call
                _patch_slot(<PyTypeObject*>pybstr, slot, DEL)
            if hasattr(pyustr, slot):   # e.g. we do not define ustr.isprintable ourselves
                _patch_slot(<PyTypeObject*>pyustr, slot, DEL)
_bstrustr_remove_unsupported_slots()


# ---- quoting ----

# _bpysmartquote_u3b2 quotes bytes/bytearray s the same way python would do for string.
#
# nonascii_escape indicates whether \xNN with NN >= 0x80 is present in the output.
#
# NOTE the return type is str type of current python, so that quoted result
# could be directly used in __repr__ or __str__ implementation.
cdef _bpysmartquote_u3b2(const byte[::1] s): # -> (unicode(py3)|bytes(py2), nonascii_escape)
    # smartquotes: choose ' or " as quoting character exactly the same way python does
    # https://github.com/python/cpython/blob/v2.7.18-0-g8d21aa21f2c/Objects/stringobject.c#L905-L909
    cdef byte quote = ord("'")
    if (quote in s) and (ord('"') not in s):
        quote = ord('"')

    cdef bint nonascii_escape
    x = strconv._quote(s, quote, &nonascii_escape)              # raw bytes
    if PY_MAJOR_VERSION < 3:
        return x, nonascii_escape
    else:
        return _utf8_decode_surrogateescape(x), nonascii_escape # raw unicode

# _upysmartquote_u3b2 is similar to _bpysmartquote_u3b2 but accepts unicode argument.
#
# NOTE the return type is str type of current python - see _bpysmartquote_u3b2 for details.
cdef _upysmartquote_u3b2(s): # -> (unicode(py3)|bytes(py2), nonascii_escape)
    assert isinstance(s, unicode), s
    return _bpysmartquote_u3b2(_utf8_encode_surrogateescape(s))


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
        obj = _bstringify(obj)
    return strconv.pyquote(obj)



# ---- _bstringify ----

# _bstringify returns string representation of obj.
# it is similar to unicode(obj), but handles bytes as UTF-8 encoded strings.
cdef _bstringify(object obj): # -> unicode|bytes
    if type(obj) in (pybstr, pyustr):
        return obj

    # indicate to e.g. patched bytes.__repr__ that it is being called from under _bstringify
    _bstringify_enter()

    try:
        if False:   # PY_MAJOR_VERSION >= 3:
            # NOTE this depends on patches to bytes.{__repr__,__str__} below
            return unicode(obj)

        else:
            # on py2 mimic manually what unicode(·) does on py3
            # the reason we do it manually is because if we try just
            # unicode(obj), and obj's __str__ returns UTF-8 bytestring, it will
            # fail with UnicodeDecodeError. Similarly if we unconditionally do
            # str(obj), it will fail if obj's __str__ returns unicode.
            #
            # NOTE this depends on patches to bytes.{__repr__,__str__} and
            #      unicode.{__repr__,__str__} below.
            if False:   # PY_MAJOR_VERSION < 3  and  hasattr(obj, '__unicode__'):
                return obj.__unicode__()    # XXX needed ?
            elif Py_TYPE(obj).tp_str != NULL:
                return Py_TYPE(obj).tp_str(obj)
            #elif hasattr(obj, '__str__'):
            #    return obj.__str__()
            else:
                return repr(obj)

    finally:
        _bstringify_leave()

# _bstringify_repr returns repr of obj.
# it is similar to repr(obj), but handles bytes as UTF-8 encoded strings.
cdef _bstringify_repr(object obj): # -> unicode|bytes
    _bstringify_enter_repr()
    try:
        return repr(obj)
    finally:
        _bstringify_leave_repr()

# patch bytes.{__repr__,__str__} and (py2) unicode.{__repr__,__str__}, so that both
# bytes and unicode are treated as normal strings when under _bstringify.
#
# Why:
#
#   py2: str([ 'β'])          ->  ['\\xce\\xb2']        (1) x
#   py2: str([u'β'])          ->  [u'\\u03b2']          (2) x
#   py3: str([ 'β'])          ->  ['β']                 (3)
#   py3: str(['β'.encode()])  ->  [b'\\xce\\xb2']       (4) x
#
# for us 3 is ok, while 1,2 and 4 are not. For all 1,2,3,4 we want e.g.
# `bstr(·)` or `b('%s') % ·` to give ['β']. This is fixed by patching __repr__.
#
# regarding patching __str__ - 6 and 8 in the following examples illustrate the
# need to do it:
#
#   py2: str( 'β')            ->  'β'                   (5)
#   py2: str(u'β')            ->  UnicodeEncodeError    (6) x
#   py3: str( 'β')            ->  'β'                   (7)
#   py3: str('β'.encode())    ->  b'\\xce\\xb2'         (8) x
#
# See also overview of %-formatting.

cdef reprfunc _bytes_tp_repr   = Py_TYPE(b'').tp_repr
cdef reprfunc _bytes_tp_str    = Py_TYPE(b'').tp_str
cdef reprfunc _unicode_tp_repr = Py_TYPE(u'').tp_repr
cdef reprfunc _unicode_tp_str  = Py_TYPE(u'').tp_str

cdef object _bytes_tp_xrepr(object s):
    bs = _inbstringify_get()
    if bs.inbstringify == 0:
        return _bytes_tp_repr(s)
    s, _ = _bpysmartquote_u3b2(s)
    if PY_MAJOR_VERSION >= 3  and  bs.inrepr != 0:
        s = 'b'+s
    return s

cdef object _bytes_tp_xstr(object s):
    bs = _inbstringify_get()
    if bs.inbstringify == 0:
        return _bytes_tp_str(s)
    else:
        if PY_MAJOR_VERSION >= 3:
            return _utf8_decode_surrogateescape(s)
        else:
            return s

cdef object _unicode2_tp_xrepr(object s):
    bs = _inbstringify_get()
    if bs.inbstringify == 0:
        return _unicode_tp_repr(s)
    s, _ = _upysmartquote_u3b2(s)
    if PY_MAJOR_VERSION < 3  and  bs.inrepr != 0:
        s = 'u'+s
    return s

cdef object _unicode2_tp_xstr(object s):
    bs = _inbstringify_get()
    if bs.inbstringify == 0:
        return _unicode_tp_str(s)
    else:
        return s

def _bytes_x__repr__(s):        return _bytes_tp_xrepr(s)
def _bytes_x__str__(s):         return _bytes_tp_xstr(s)
def _unicode2_x__repr__(s):     return _unicode2_tp_xrepr(s)
def _unicode2_x__str__(s):      return _unicode2_tp_xstr(s)

def _():
    cdef PyTypeObject* t
    # NOTE patching bytes and its already-created subclasses that did not override .tp_repr/.tp_str
    # NOTE if we don't also patch __dict__ - e.g. x.__repr__() won't go through patched .tp_repr
    for pyt in [bytes] + bytes.__subclasses__():
        assert isinstance(pyt, type)
        t = <PyTypeObject*>pyt
        if t.tp_repr == _bytes_tp_repr:
            t.tp_repr = _bytes_tp_xrepr
            _patch_slot(t, '__repr__', _bytes_x__repr__)
        if t.tp_str  == _bytes_tp_str:
            t.tp_str  = _bytes_tp_xstr
            _patch_slot(t, '__str__',  _bytes_x__str__)
_()

if PY_MAJOR_VERSION < 3:
    def _():
        cdef PyTypeObject* t
        for pyt in [unicode] + unicode.__subclasses__():
            assert isinstance(pyt, type)
            t = <PyTypeObject*>pyt
            if t.tp_repr == _unicode_tp_repr:
                t.tp_repr = _unicode2_tp_xrepr
                _patch_slot(t, '__repr__', _unicode2_x__repr__)
            if t.tp_str  == _unicode_tp_str:
                t.tp_str  = _unicode2_tp_xstr
                _patch_slot(t, '__str__',  _unicode2_x__str__)
    _()


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


# patch bytearray.{__repr__,__str__} similarly to bytes, so that e.g.
# '%s' % bytearray('β')   turns into β      instead of  bytearray(b'\xce\xb2'),   and
# '%s' % [bytearray('β']  turns into ['β']  instead of  [bytearray(b'\xce\xb2')].
#
# also patch:
#
# - bytearray.__init__ to accept ustr instead of raising 'TypeError:
#   string argument without an encoding'  (pybug: bytearray() should respect
#   __bytes__ similarly to bytes)
#
# - bytearray.{sq_concat,sq_inplace_concat} to accept ustr instead of raising
#   TypeError.  (pybug: bytearray + and += should respect __bytes__)
cdef reprfunc   _bytearray_tp_repr    = (<PyTypeObject*>bytearray) .tp_repr
cdef reprfunc   _bytearray_tp_str     = (<PyTypeObject*>bytearray) .tp_str
cdef initproc   _bytearray_tp_init    = (<_XPyTypeObject*>bytearray) .tp_init
cdef binaryfunc _bytearray_sq_concat  = (<_XPyTypeObject*>bytearray) .tp_as_sequence.sq_concat
cdef binaryfunc _bytearray_sq_iconcat = (<_XPyTypeObject*>bytearray) .tp_as_sequence.sq_inplace_concat

cdef object _bytearray_tp_xrepr(object a):
    bs = _inbstringify_get()
    if bs.inbstringify == 0:
        return _bytearray_tp_repr(a)
    s, _ = _bpysmartquote_u3b2(a)
    if bs.inrepr != 0:
        s = 'bytearray(b' + s + ')'
    return s

cdef object _bytearray_tp_xstr(object a):
    bs = _inbstringify_get()
    if bs.inbstringify == 0:
        return _bytearray_tp_str(a)
    else:
        if PY_MAJOR_VERSION >= 3:
            return _utf8_decode_surrogateescape(a)
        else:
            return _bytearray_data(a)


cdef int _bytearray_tp_xinit(object self, PyObject* args, PyObject* kw) except -1:
    if args != NULL  and  (kw == NULL  or  (not <object>kw)):
        argv = <object>args
        if isinstance(argv, tuple)  and  len(argv) == 1:
            arg = argv[0]
            if isinstance(arg, pyustr):
                argv = (pyb(arg),)      # NOTE argv is kept alive till end of function
                args = <PyObject*>argv  #      no need to incref it
    return _bytearray_tp_init(self, args, kw)


cdef object _bytearray_sq_xconcat(object a, object b):
    if isinstance(b, pyustr):
        b = pyb(b)
    return _bytearray_sq_concat(a, b)

cdef object _bytearray_sq_xiconcat(object a, object b):
    if isinstance(b, pyustr):
        b = pyb(b)
    return _bytearray_sq_iconcat(a, b)


def _bytearray_x__repr__(a):    return _bytearray_tp_xrepr(a)
def _bytearray_x__str__ (a):    return _bytearray_tp_xstr(a)
def _bytearray_x__init__(self, *argv, **kw):
    # NOTE don't return - just call: __init__ should return None
    _bytearray_tp_xinit(self, <PyObject*>argv, <PyObject*>kw)
def _bytearray_x__add__ (a, b): return _bytearray_sq_xconcat(a, b)
def _bytearray_x__iadd__(a, b): return _bytearray_sq_xiconcat(a, b)

def _():
    cdef PyTypeObject* t
    for pyt in [bytearray] + bytearray.__subclasses__():
        assert isinstance(pyt, type)
        t = <PyTypeObject*>pyt
        if t.tp_repr == _bytearray_tp_repr:
            t.tp_repr = _bytearray_tp_xrepr
            _patch_slot(t, '__repr__', _bytearray_x__repr__)
        if t.tp_str  == _bytearray_tp_str:
            t.tp_str  = _bytearray_tp_xstr
            _patch_slot(t, '__str__',  _bytearray_x__str__)
        t_ = <_XPyTypeObject*>t
        if t_.tp_init == _bytearray_tp_init:
            t_.tp_init = _bytearray_tp_xinit
            _patch_slot(t, '__init__', _bytearray_x__init__)
        t_sq = t_.tp_as_sequence
        if t_sq.sq_concat == _bytearray_sq_concat:
            t_sq.sq_concat = _bytearray_sq_xconcat
            _patch_slot(t, '__add__',  _bytearray_x__add__)
        if t_sq.sq_inplace_concat == _bytearray_sq_iconcat:
            t_sq.sq_inplace_concat = _bytearray_sq_xiconcat
            _patch_slot(t, '__iadd__', _bytearray_x__iadd__)
_()


# _bytearray_data return raw data in bytearray as bytes.
# XXX `bytearray s` leads to `TypeError: Expected bytearray, got hbytearray`
cdef bytes _bytearray_data(object s):
    if PY_MAJOR_VERSION >= 3:
        return bytes(s)
    else:
        # on py2 bytes(s) is str(s) which invokes patched bytearray.__str__
        # we want to get raw bytearray data, which is provided by unpatched bytearray.__str__
        return _bytearray_tp_str(s)


# _bstringify_enter*/_bstringify_leave*/_inbstringify_get allow _bstringify* to
# indicate to further invoked code whether it has been invoked from under
# _bstringify* or not.
cdef object _inbstringify_key = "golang._inbstringify"
@final
cdef class _InBStringify:
    cdef int inbstringify   # >0 if we are running under _bstringify/_bstringify_repr
    cdef int inrepr         # >0 if we are running under             _bstringify_repr
    def __cinit__(self):
        self.inbstringify = 0
        self.inrepr       = 0

cdef void _bstringify_enter() except*:
    bs = _inbstringify_get()
    bs.inbstringify += 1

cdef void _bstringify_leave() except*:
    bs = _inbstringify_get()
    bs.inbstringify -= 1

cdef void _bstringify_enter_repr() except*:
    bs = _inbstringify_get()
    bs.inbstringify += 1
    bs.inrepr       += 1

cdef void _bstringify_leave_repr() except*:
    bs = _inbstringify_get()
    bs.inbstringify -= 1
    bs.inrepr       -= 1

cdef _InBStringify _inbstringify_get():
    cdef PyObject*  _ts_dict = PyThreadState_GetDict() # borrowed
    if _ts_dict == NULL:
        raise RuntimeError("no thread state")
    cdef _InBStringify ts_inbstringify
    cdef PyObject* _ts_inbstrinfigy = PyDict_GetItemWithError(<object>_ts_dict, _inbstringify_key) # raises on error
    if _ts_inbstrinfigy == NULL:
        # key not present
        ts_inbstringify = _InBStringify()
        PyDict_SetItem(<object>_ts_dict, _inbstringify_key, ts_inbstringify)
    else:
        ts_inbstringify = <_InBStringify>_ts_inbstrinfigy
    return ts_inbstringify


# XXX text
cdef _get_slot(PyTypeObject* typ, str name):
    typdict = <dict>(typ.tp_dict)
    return typdict[name]

# _patch_slot installs func_or_descr into typ's __dict__ as name.
#
# if func_or_descr is descriptor (has __get__), or asis=True, it is installed as is.
# otherwise it is wrapped with "unbound method" descriptor.
#
# if func_or_descr is DEL the slot is removed from typ's __dict__.
cdef DEL = object()
cdef _patch_slot(PyTypeObject* typ, str name, object func_or_descr, asis=False):
    typdict = <dict>(typ.tp_dict)
    #print("\npatching %s.%s  with  %r" % (typ.tp_name, name, func_or_descr))
    #print("old:  %r" % typdict.get(name))

    if hasattr(func_or_descr, '__get__')  or  func_or_descr is DEL  or  asis:
        descr = func_or_descr
    else:
        func = func_or_descr
        if PY_MAJOR_VERSION < 3:
            descr = pytypes.MethodType(func, None, <object>typ)
        else:
            descr = _UnboundMethod(func)

    if descr is DEL:
        del typdict[name]
    else:
        typdict[name] = descr
    #print("new:  %r" % typdict.get(name))
    PyType_Modified(typ)


cdef class _UnboundMethod(object): # they removed unbound methods on py3
    cdef object func
    def __init__(self, func):
        self.func = func
    def __get__(self, obj, objtype):
        return pyfunctools.partial(self.func, obj)


# ---- % formatting ----

# When formatting string is bstr/ustr we treat bytes in all arguments as
# UTF8-encoded bytestrings. The following approach is used to implement this:
#
# 1. both bstr and ustr format via bytes-based _bprintf.
# 2. we parse the format string and handle every formatting specifier separately:
# 3. for formats besides %s/%r we use bytes.__mod__ directly.
#
# 4. for %s we stringify corresponding argument specially with all, potentially
#    internal, bytes instances treated as UTF8-encoded strings:
#
#       '%s' % b'\xce\xb2'      ->  "β"
#       '%s' % [b'\xce\xb2']    ->  "['β']"
#
# 5. for %r, similarly to %s, we prepare repr of corresponding argument
#    specially with all, potentially internal, bytes instances also treated as
#    UTF8-encoded strings:
#
#       '%r' % b'\xce\xb2'      ->  "b'β'"
#       '%r' % [b'\xce\xb2']    ->  "[b'β']"
#
#
# For "2" we implement %-format parsing ourselves. test_strings_mod_and_format
# has good coverage for this phase to make sure we get it right and behaving
# exactly the same way as standard Python does.
#
# For "4" we monkey-patch bytes.__repr__ to repr bytes as strings when called
# from under bstr.__mod__(). See _bstringify for details.
#
# For "5", similarly to "4", we rely on adjustments to bytes.__repr__ .
# See _bstringify_repr for details.
#
# See also overview of patching bytes.{__repr__,__str__} near _bstringify.
cdef object _missing  = object()
cdef object _atidx_re = pyre.compile('.* at index ([0-9]+)$')
cdef _bprintf(const byte[::1] fmt, xarg): # -> pybstr
    cdef bytearray out = bytearray()

    cdef object argv = None  # if xarg is tuple or subclass
    cdef object argm = None  # if xarg is mapping

    # https://github.com/python/cpython/blob/2.7-0-g8d21aa21f2c/Objects/stringobject.c#L4298-L4300
    # https://github.com/python/cpython/blob/v3.11.0b1-171-g70aa1b9b912/Objects/unicodeobject.c#L14319-L14320
    if _XPyMapping_Check(xarg)   and \
       (not isinstance(xarg, tuple))    and \
       (not isinstance(xarg, (bytes,unicode))):
        argm = xarg

    if isinstance(xarg, tuple):
        argv = xarg
        xarg = _missing

    #print()
    #print('argv:', argv)
    #print('argm:', argm)
    #print('xarg:', xarg)

    cdef int argv_idx = 0
    def nextarg():
        nonlocal argv_idx, xarg
        # NOTE for `'%s %(x)s' % {'x':1}`  python gives  "{'x': 1} 1"
        # -> so we avoid argm check completely here
        #if argm is not None:
        if 0:
            raise ValueError('mixing dict/tuple')

        elif argv is not None:
            # tuple xarg
            if argv_idx < len(argv):
                arg = argv[argv_idx]
                argv_idx += 1
                return arg

        elif xarg is not _missing:
            # sole xarg
            arg = xarg
            xarg = _missing
            return arg

        raise TypeError('not enough arguments for format string')

    def badf():
        raise ValueError('incomplete format')

    # parse format string locating formatting specifiers
    # if we see %s/%r - use _bstringify
    # else use builtin %-formatting
    #
    #   %[(name)][flags][width|*][.[prec|*]][len](type)
    #
    # https://docs.python.org/3/library/stdtypes.html#printf-style-string-formatting
    # https://github.com/python/cpython/blob/2.7-0-g8d21aa21f2c/Objects/stringobject.c#L4266-L4765
    #
    # Rejected alternative: try to format; if we get "TypeError: %b requires a
    # bytes-like object ..." retry with that argument converted to bstr.
    #
    # Rejected because e.g. for  `%(x)s %(x)r` % {'x': obj}`  we need to use
    # access number instead of key 'x' to determine which accesses to
    # bstringify. We could do that, but unfortunately on Python2 the access
    # number is not easily predictable because string could be upgraded to
    # unicode in the midst of being formatted and so some access keys will be
    # accesses not once.
    #
    # Another reason for rejection: b'%r' and u'%r' handle arguments
    # differently - on b %r is aliased to %a.
    cdef int i = 0
    cdef int l = len(fmt)
    cdef byte c
    while i < l:
        c  = fmt[i]
        i += 1
        if c != ord('%'):
            out.append(c)
            continue

        fmt_istart = i-1
        nameb = _missing
        width = _missing
        prec  = _missing
        value = _missing

        # `c = fmt_nextchar()`  avoiding https://github.com/cython/cython/issues/4798
        if i >= l: badf()
        c = fmt[i]; i += 1

        # (name)
        if c == ord('('):
            #print('(name)')
            if argm is None:
                raise TypeError('format requires a mapping')
            nparen = 1
            nameb = b''
            while 1:
                if i >= l:
                    raise ValueError('incomplete format key')
                c = fmt[i]; i += 1
                if c == ord('('):
                    nparen += 1
                elif c == ord(')'):
                    nparen -= 1
                    if i >= l: badf()
                    c = fmt[i]; i += 1
                    break
                else:
                    nameb += bchr(c)

        # flags
        while chr(c) in '#0- +':
            #print('flags')
            if i >= l: badf()
            c = fmt[i]; i += 1

        # [width|*]
        if c == ord('*'):
            #print('*width')
            width = nextarg()
            if i >= l: badf()
            c = fmt[i]; i += 1
        else:
            while chr(c).isdigit():
                #print('width')
                if i >= l: badf()
                c = fmt[i]; i += 1

        # [.prec|*]
        if c == ord('.'):
            #print('dot')
            if i >= l: badf()
            c = fmt[i]; i += 1
            if c == ord('*'):
                #print('.*')
                prec = nextarg()
                if i >= l: badf()
                c = fmt[i]; i += 1
            else:
                while chr(c).isdigit():
                    #print('.prec')
                    if i >= l: badf()
                    c = fmt[i]; i += 1

        # [len]
        while chr(c) in 'hlL':
            #print('len')
            if i >= l: badf()
            c = fmt[i]; i += 1

        fmt_type = c
        #print('fmt_type:', repr(chr(fmt_type)))

        if fmt_type == ord('%'):
            if i-2 == fmt_istart:   # %%
                out.append(b'%')
                continue

        if nameb is not _missing:
            xarg = _missing # `'%(x)s %s' % {'x':1}`  raises "not enough arguments"
            nameu = _utf8_decode_surrogateescape(nameb)
            try:
                value = argm[nameb]
            except KeyError:
                # retry with changing key via bytes <-> unicode
                # e.g. for `b('%(x)s') % {'x': ...}` builtin bytes.__mod__ will
                # extract b'x' as key and raise KeyError: b'x'. We avoid that via
                # retrying with second string type for key.
                value = argm[nameu]
        else:
            # NOTE for `'%4%' % ()` python raises "not enough arguments ..."
            #if fmt_type != ord('%'):
            if 1:
                value = nextarg()

        if fmt_type == ord('%'):
            raise ValueError("unsupported format character '%s' (0x%x) at index %i" % (chr(c), c, i-1))

        fmt1 = memoryview(fmt[fmt_istart:i]).tobytes()
        #print('fmt_istart:', fmt_istart)
        #print('i:         ', i)
        #print(' ~> __mod__ ', repr(fmt1))

        # bytes %r is aliased of %a (ASCII), but we want unicode-like %r
        # -> handle it ourselves
        if fmt_type == ord('r'):
            value = pyb(_bstringify_repr(value))
            fmt_type = ord('s')
            fmt1 = fmt1[:-1] + b's'

        elif fmt_type == ord('s'):
            # %s -> feed value through _bstringify
            # this also converts e.g. int to bstr, else e.g. on `b'%s' % 123` python
            # complains '%b requires a bytes-like object ...'
            value = pyb(_bstringify(value))

        if nameb is not _missing:
            arg = {nameb: value, nameu: value}
        else:
            t = []
            if width is not _missing:   t.append(width)
            if prec  is not _missing:   t.append(prec)
            if value is not _missing:   t.append(value)
            t = tuple(t)
            arg = t

        #print('--> __mod__ ', repr(fmt1), ' % ', repr(arg))
        try:
            IF PY2:
                # NOTE not zbytes.__mod__ because underlying PyBytes_Format is patched
                s = _pbytes_Format(fmt1, arg)
            ELSE:
                s = zbytes.__mod__(fmt1, arg)
        except ValueError as e:
            # adjust position in '... at index <idx>' from fmt1 to fmt
            if len(e.args) == 1:
                a = e.args[0]
                m = _atidx_re.match(a)
                if m is not None:
                    a = a[:m.start(1)] + str(i-1)
                    e.args = (a,)
            raise
        out.extend(s)

    if argm is None:
        #print('END')
        #print('argv:', argv, 'argv_idx:', argv_idx, 'xarg:', xarg)
        if (argv is not None  and  argv_idx != len(argv))  or  (xarg is not _missing):
            raise TypeError("not all arguments converted during string formatting")

    return pybstr(out)


# ---- .format formatting ----

# Handling .format is easier and similar to %-Formatting: we detect fields to
# format as strings via using custom string.Formatter (see _BFormatter), and
# further treat objects to stringify similarly to how %-formatting does for %s and %r.
#
# We do not need to implement format parsing ourselves, because
# string.Formatter provides it.

# _bvformat implements .format for pybstr/pyustr.
cdef _bvformat(fmt, args, kw):
    return _BFormatter().vformat(fmt, args, kw)

class _BFormatter(pystring.Formatter):
    def format_field(self, v, fmtspec):
        #print('format_field', repr(v), repr(fmtspec))
        # {} on bytes/bytearray  ->  treat it as bytestring
        if type(v) in (bytes, bytearray):
            v = pyb(v)
        #print('  ~ ', repr(v))
        # if the object contains bytes inside, e.g. as in [b'β'] - treat those
        # internal bytes also as bytestrings
        _bstringify_enter()
        try:
            #return super(_BFormatter, self).format_field(v, fmtspec)
            x = super(_BFormatter, self).format_field(v, fmtspec)
        finally:
            _bstringify_leave()
        #print('  ->', repr(x))
        if PY_MAJOR_VERSION < 3:  # py2 Formatter._vformat does does ''.join(result)
            x = pyu(x)            # -> we want everything in result to be unicode to avoid
                                  # UnicodeDecodeError
        return x

    def convert_field(self, v, conv):
        #print('convert_field', repr(v), repr(conv))
        if conv == 's':
            # string.Formatter does str(v) for 's'. we don't want that:
            # py3: stringify, and especially treat bytes as bytestring
            # py2: stringify, avoiding e.g. UnicodeEncodeError for str(unicode)
            x = pyb(_bstringify(v))
        elif conv == 'r':
            # for bytes {!r} produces ASCII-only, but we want unicode-like !r for e.g. b'β'
            # -> handle it ourselves
            x = pyb(_bstringify_repr(v))
        else:
            x = super(_BFormatter, self).convert_field(v, conv)
        #print('  ->', repr(x))
        return x

    # on py2 string.Formatter does not handle field autonumbering
    # -> do it ourselves
    if PY_MAJOR_VERSION < 3:
        _autoidx   = 0
        _had_digit = False
        def get_field(self, field_name, args, kwargs):
            if field_name == '':
                if self._had_digit:
                    raise ValueError("mixing explicit and auto numbered fields is forbidden")
                field_name = str(self._autoidx)
                self._autoidx += 1

            elif field_name.isdigit():
                self._had_digit = True
                if self._autoidx != 0:
                    raise ValueError("mixing explicit and auto numbered fields is forbidden")

            return super(_BFormatter, self).get_field(field_name, args, kwargs)


# XXX place, comments
# str % ... : ceval on py2 and py3 < 3.11 invokes PyString_Format / PyUnicode_Format
#   directly upon seeing BINARY_MODULO. This leads to bstr.__mod__ not being called.
ctypedef unicode uformatfunc(object, object)
ctypedef bytes   bformatfunc(object, object)
cdef uformatfunc* _punicode_Format = PyUnicode_Format
cdef unicode _unicode_xFormat(object s, object args):
    return pyustr.__mod__(s, args)

IF PY2:
    cdef bformatfunc* _pbytes_Format = PyBytes_Format
    cdef _bytes_xFormat(object s, object args):
        return pybstr.__mod__(s, args)

cdef _patch_capi_str_format():
    cpatch(<void**>&_punicode_Format, <void*>_unicode_xFormat)
    IF PY2:
        cpatch(<void**>&_pbytes_Format, <void*>_bytes_xFormat)


# XXX place, comments, test
#py3.11: specializes instructions. e.g. ustr(obj) will specialize (after
#    executing 8 times) to directly invoke
#
#   PyObject_Str(obj)
#
#    which, if obj is e.g. b'123' will return "b'123'" instead of "123".
#
#    -> if we patch str=ustr, we need to patch PyObject_Str as well.
#    -> XXX and check all other specializations.
#
# NOTE also good to just do
cdef _object_xStr(object s):
    IF PY2:
        return pybstr(s)
    ELSE:
        return pyustr(s)
ctypedef object objstrfunc(object)
cdef objstrfunc* _pobject_Str = PyObject_Str
cdef  _patch_capi_object_str():
    cpatch(<void**>&_pobject_Str, <void*>_object_xStr)



# ---- misc ----

cdef object _xpyu_coerce(obj):
    return _pyu_coerce(obj) if obj is not None else None

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

cdef extern from "Python.h":
    """
    static int _XPyMapping_Check(PyObject *o) {
    #if PY_MAJOR_VERSION >= 3
        return PyMapping_Check(o);
    #else
        // on py2 PyMapping_Check besides checking tp_as_mapping->mp_subscript
        // also verifies !tp_as_sequence->sq_slice. We want to avoid that
        // because PyString_Format checks only tp_as_mapping->mp_subscript.
        return Py_TYPE(o)->tp_as_mapping && Py_TYPE(o)->tp_as_mapping->mp_subscript;
    #endif
    }
    """
    bint _XPyMapping_Check(object o)


# ---- UTF-8 encode/decode ----

# TODO(kirr) adjust UTF-8 encode/decode surrogateescape(*) a bit so that not
# only bytes -> unicode -> bytes is always identity for any bytes (this is
# already true), but also that unicode -> bytes -> unicode is also always true
# for all unicode codepoints.
#
# The latter currently fails for all surrogate codepoints outside of U+DC80..U+DCFF range:
#
#   In [1]: x = u'\udc00'
#
#   In [2]: x.encode('utf-8')
#   UnicodeEncodeError: 'utf-8' codec can't encode character '\udc00' in position 0: surrogates not allowed
#
#   In [3]: x.encode('utf-8', 'surrogateescape')
#   UnicodeEncodeError: 'utf-8' codec can't encode character '\udc00' in position 0: surrogates not allowed
#
# (*) aka UTF-8b (see http://hyperreal.org/~est/utf-8b/releases/utf-8b-20060413043934/kuhn-utf-8b.html)

from six import unichr                      # py2: unichr       py3: chr
from six import int2byte as bchr            # py2: chr          py3: lambda x: bytes((x,))

# XXX turn vvv into compile-time constant
cdef bint _ucs2_build = (sys.maxunicode ==     0xffff)      #    ucs2
assert    _ucs2_build or sys.maxunicode >= 0x0010ffff       # or ucs4

# _utf8_decode_rune decodes next UTF8-character from byte string s.
#
# _utf8_decode_rune(s) -> (r, size)
cdef (rune, int) _utf8_decode_rune(const byte[::1] s):
    if len(s) == 0:
        return utf8.RuneError, 0

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
            # py: TypeError: ord() expected a character, but string of length 2 found
            # cy: ValueError: only single character unicode strings can be converted to Py_UCS4, got length 2
            except (TypeError, ValueError):
                l -= 1
                continue

        l -= 1
        continue

    # invalid UTF-8
    return utf8.RuneError, 1


# _utf8_decode_surrogateescape mimics s.decode('utf-8', 'surrogateescape') from py3.
cdef _utf8_decode_surrogateescape(const byte[::1] s): # -> unicode
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
        if r == utf8.RuneError  and  width == 1:
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
cdef _utf8_encode_surrogateescape(s): # -> bytes
    assert isinstance(s, unicode)
    if PY_MAJOR_VERSION >= 3:
        return zunicode.encode(s, 'UTF-8', 'surrogateescape')

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
# represented as 2 unicode points.
cdef unicode _xunichr(rune i):
    if not _ucs2_build:
        return unichr(i)
    else:
        if i < 0x10000:
            return unichr(i)

        # see _utf8_encode_surrogateescape for details
        uh = i - 0x10000
        return unichr(0xd800 + (uh >> 10)) + \
               unichr(0xdc00 + (uh & 0x3ff))


# ---- funchook wrappers -----

cdef funchook_t* xfunchook_create() except NULL:
    h = funchook_create()
    if h == NULL:
        raise MemoryError()
    return h

cdef xfunchook_destroy(funchook_t* h):
    err = funchook_destroy(h)
    if err != 0:
        raise RuntimeError(funchook_error_message(h))

cdef xfunchook_prepare(funchook_t* h, void** target_func, void* hook_func):
    err = funchook_prepare(h, target_func, hook_func)
    if err != 0:
        raise RuntimeError(funchook_error_message(h))

cdef xfunchook_install(funchook_t* h, int flags):
    err = funchook_install(h, flags)
    if err != 0:
        raise RuntimeError(funchook_error_message(h))

cdef xfunchook_uninstall(funchook_t* h, int flags):
    err = funchook_uninstall(h, flags)
    if err != 0:
        raise RuntimeError(funchook_error_message(h))

# cpatch = xfunchook_prepare on _patch_capi_hook
cdef cpatch(void** target_func, void* hook_func):
    assert target_func[0] != NULL
    xfunchook_prepare(_patch_capi_hook, target_func, hook_func)


# ---- patch unicode/str types to be ustr/bstr under gpython ----
# XXX make sure original _pybstr/_pyustr cannot be used after patching      XXX right ?
# XXX and make sure golang._golang._pybstr cannot be imported as well  (ex pickle)
# XXX ._pyustr.__module__ = 'builtins' after patch      - why?

def _():
    gpy_strings = getattr(sys, '_gpy_strings', None)
    if gpy_strings == 'bstr+ustr':
        _patch_str()
    elif gpy_strings in ('pystd', None):
        pass
    else:
        raise AssertionError("invalid sys._gpy_strings: %r" % (gpy_strings,))
_()

# _patch_str is invoked when gpython imports golang and instructs to replace
# builtin str/unicode types with bstr/ustr.
#
# After the patch is applied all existing objects that have e.g. unicode type
# will switch to having ustr type.
cdef PyTypeObject _unicode_orig
cdef PyTypeObject _bytes_orig
cdef funchook_t* _patch_capi_hook
cdef _patch_str():
    global zbytes,   _bytes_orig,   pybstr
    global zunicode, _unicode_orig, pyustr
    global _patch_capi_hook

    #print('\n\nPATCH\n\n')

    # XXX explain
    bpreserve_slots = upreserve_slots = ("maketrans",)
    if PY_MAJOR_VERSION < 3:
        bpreserve_slots += ("encode",) # @property'ies
        upreserve_slots += ("decode",)

    # patch unicode to be pyustr. This patches
    # - unicode (py2)
    # - str     (py3)
    _pytype_clone(<PyTypeObject*>unicode, &_unicode_orig, "unicode(pystd)")
    Py_INCREF(unicode)  # XXX needed?
    zunicode = <object>&_unicode_orig

    _pytype_replace_by_child(
            <PyTypeObject*>unicode, &_unicode_orig,
            <PyTypeObject*>pyustr, "ustr(origin)",
            upreserve_slots)
    pyustr = unicode    # retarget pyustr -> unicode to where it was copied
    # XXX vvv needed so that patched unicode could be saved by py2:cPickle at all
    (<PyTypeObject*>pyustr).tp_name = ("unicode" if PY_MAJOR_VERSION < 3  else "str")

    # py2: patch str to be pybstr
    if PY_MAJOR_VERSION < 3:
        _pytype_clone(<PyTypeObject*>bytes, &_bytes_orig, "bytes(pystd)")
        Py_INCREF(bytes)    # XXX needed?
        zbytes = <object>&_bytes_orig

        _pytype_replace_by_child(
                <PyTypeObject*>bytes, &_bytes_orig,
                <PyTypeObject*>_pybstr, "bstr(origin)",
                bpreserve_slots)
        pybstr = bytes  # retarget pybstr -> bytes to where it was copied
        (<PyTypeObject*>pybstr).tp_name = ("str" if PY_MAJOR_VERSION < 3  else "bytes")

    # need to remove unsupported slots in cloned bstr/ustr again since PyType_Ready might have recreated them
    _bstrustr_remove_unsupported_slots()


    # also patch UserString to have methods that bstr/ustr have
    # else e.g. IPython's guarded_eval.py fails in `_list_methods(collections.UserString, dir(str))`
    from six.moves import UserString
    def userstr__bytes__(s):    return bytes(s.data)
    def userstr__unicode__(s):  return unicode(s.data)
    assert not hasattr(UserString, '__bytes__')         # XXX test
    assert not hasattr(UserString, '__unicode__')
    UserString.__bytes__   = userstr__bytes__
    UserString.__unicode__ = userstr__unicode__

    # XXX also patch CAPI functions ... XXX explain
    #funchook_set_debug_file("/dev/stderr")
    _patch_capi_hook = xfunchook_create()

    _patch_capi_str_format()
    _patch_capi_object_str()
    _patch_capi_unicode_decode_as_bstr()
    _patch_str_pickle()
    # ...

    xfunchook_install(_patch_capi_hook, 0)


# XXX place ok ?
include '_golang_str_pickle.pyx'

# _pytype_clone clones PyTypeObject src into dst.
# dst must not be previously initialized.
#
# dst will have reference-count = 1 meaning new reference to it is returned.
cdef _pytype_clone(PyTypeObject *src, PyTypeObject *dst, const char* new_name):
    assert (src.tp_flags & Py_TPFLAGS_READY) != 0
    assert (src.tp_flags & Py_TPFLAGS_HEAPTYPE) == 0    # src is not allocated on heap
    #assert not PyType_IS_GC((<PyObject*>src).ob_type)  # XXX not true as unicode.ob_type is PyType_Type
                                                        #     which generally has GC support, but
                                                        #     GC is deactivated for non-heap types.
    # copy the struct   XXX + .ob_next / .ob_prev (Py_TRACE_REFS)
    dst[0] = src[0]
    (<PyObject*>dst).ob_refcnt = 1

    if new_name != NULL:
        dst.tp_name = new_name

    # now reinitialize things like .tp_dict etc, where PyType_Ready built slots that point to src.
    # we want all those slots to be rebuilt and point to dst instead.
    _dst = <_XPyTypeObject*>dst
    dst .tp_flags &= ~Py_TPFLAGS_READY
    dst .tp_dict     = NULL
    _dst.tp_bases    = NULL
    _dst.tp_mro      = NULL
    _dst.tp_cache    = NULL
    _dst.tp_weaklist = NULL

    # dst.__subclasses__ will be empty because existing children inherit from src, not from dst.
    _dst.tp_subclasses = NULL

    PyType_Ready(<object>dst)
    assert (dst.tp_flags & Py_TPFLAGS_READY) != 0

# _pytype_replace_by_child replaces typ by its child egg.
#
# All existing objects that have type typ will switch to having type egg' .
# The instance/inheritance diagram for existing objects and types will switch
# as depicted below:
#
#           base                    base
#            ↑                           ↖
#           typ        ------>      egg' → typ_clone
#          ↗ ↑ ↖                   ↗ ↑       ↗
#   objects  X  egg         objects  X   egg
#            ↑                       ↑
#            Y                       Y
#
# typ_clone must be initialized via _pytype_clone(typ, typ_clone).
# egg' is egg clone put inplace of typ
#
# XXX preserve_slots - describe
cdef _pytype_replace_by_child(PyTypeObject *typ, PyTypeObject *typ_clone,
                              PyTypeObject *egg, const char* egg_old_name,
                              preserve_slots):
    otyp = <PyObject*>typ           ; oegg = <PyObject*>egg
    vtyp = <PyVarObject*>typ        ; vegg = <PyVarObject*>egg
    _typ = <_XPyTypeObject*>typ     ; _egg = <_XPyTypeObject*>egg

    assert egg.tp_base == typ
    assert _egg.tp_subclasses == NULL

    assert (typ.tp_flags & Py_TPFLAGS_READY)  != 0
    assert (egg.tp_flags & Py_TPFLAGS_READY)  != 0

    assert (typ.tp_flags & Py_TPFLAGS_HEAPTYPE) == 0
    assert (egg.tp_flags & Py_TPFLAGS_HEAPTYPE) == 0 # XXX will be not true
                                                     # -> ! Py_TPFLAGS_HAVE_GC
                                                     # -> ? set Py_TPFLAGS_HEAPTYPE back on typ' ?

    # (generally not required)
    assert (typ.tp_flags & Py_TPFLAGS_HAVE_GC) == 0
    assert (egg.tp_flags & Py_TPFLAGS_HAVE_GC) == 0
    # XXX also check PyObject_IS_GC  (verifies .tp_is_gc() = n)  ?


    assert vtyp.ob_size               ==  vegg.ob_size
    assert typ .tp_basicsize          ==  egg .tp_basicsize
    assert typ .tp_itemsize           ==  egg .tp_itemsize
    IF PY3:
        assert _typ.tp_vectorcall_offset  ==  _egg.tp_vectorcall_offset
    assert _typ.tp_weaklistoffset     ==  _egg.tp_weaklistoffset
    assert typ .tp_dictoffset         ==  egg .tp_dictoffset

    # since egg will change .tp_base it will also need to reinitialize
    # .tp_bases, .tp_mro and friends. Retrieve egg slots to preserve before we
    # clear egg.__dict__ . This covers e.g. @staticmethod and @property.
    keep_slots = {}  # name -> slot
    for name in preserve_slots:
        keep_slots[name] = _get_slot(egg, name)

    # egg: clear what PyType_Ready will recompute
    Py_CLEAR(egg .tp_dict)
    Py_CLEAR(_egg.tp_bases)
    Py_CLEAR(_egg.tp_mro)
    Py_CLEAR(_egg.tp_cache)

    # typ <- egg  preserving original typ's refcnt, weak references and subclasses\egg.
    # typ will be now playing the role of egg
    typ_refcnt     = otyp.ob_refcnt
    typ_weaklist   = _typ.tp_weaklist
    typ_subclasses = _typ.tp_subclasses
    typ[0] = egg[0]
    otyp.ob_refcnt     = typ_refcnt
    _typ.tp_weaklist   = typ_weaklist
    _typ.tp_subclasses = typ_subclasses # XXX need to remove egg from here

    # adjust .tp_base
    typ.tp_base = typ_clone
    egg.tp_base = typ_clone

    # adjust egg.tp_name
    if egg_old_name != NULL:
        egg.tp_name = egg_old_name

    # reinitialize .tp_bases, .tp_mro. .tp_cache, and recompute slots that
    # live in .tp_dict and point to their type. Do it for both typ (new egg)
    # and origin egg for generality, even though original egg won't be used
    # anymore.
    typ.tp_flags &= ~Py_TPFLAGS_READY
    egg.tp_flags &= ~Py_TPFLAGS_READY
    PyType_Ready(<object>typ)
    PyType_Ready(<object>egg)
    assert (typ.tp_flags & Py_TPFLAGS_READY) != 0
    assert (egg.tp_flags & Py_TPFLAGS_READY) != 0

    # restore slots we were asked to preserve as is
    # since those slots are e.g. @staticmethods they go to both egg' and egg.
    for name, slot in keep_slots.items():
        _patch_slot(typ, name, slot, asis=True)
        _patch_slot(egg, name, slot, asis=True)

    # XXX remove egg from typ.tp_subclasses     (also possible via setting .__bases__)
    # XXX remove typ from base.tp_subclasses
    #     else e.g. ustr(origin) is reported to be subclass of ustr by help()
    #     (pyustr.__subclasses__()  give it)

    # rebuild .tp_mro of all other typ's children
    # initially X.__mro__ = (X, typ, base) and without rebuilding it would
    # remain (X, egg', base) instead of correct (X, egg' typ_clone, base)
    # XXX py3 does this automatically?  XXX -> no, it can invalidate .__mro__, but not .tp_mro
    def refresh(x):
        assert isinstance(x, type)
        xtyp  = <PyTypeObject*>x
        _xtyp = <_XPyTypeObject*>x
        #fprintf(stderr, 'refreshing %s\n', xtyp.tp_name)
        assert (xtyp.tp_flags & Py_TPFLAGS_READY) != 0
        xtyp.tp_flags &= ~Py_TPFLAGS_READY
        Py_CLEAR(_xtyp.tp_mro)
        PyType_Ready(x)
        assert (xtyp.tp_flags & Py_TPFLAGS_READY) != 0
        for _ in x.__subclasses__():
            refresh(_)
    for _ in (<object>typ).__subclasses__():
        refresh(_)

    # XXX also preserve ._ob_next + ._ob_prev  (present in Py_TRACE_REFS builds)
