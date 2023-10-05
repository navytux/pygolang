# -*- coding: utf-8 -*-
# Copyright (C) 2023  Nexedi SA and Contributors.
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
"""_golang_str_pickle.pyx complements _golang_str.pyx and keeps everything
related to pickling strings.

It is included from _golang_str.pyx .

The main entry-points are _patch_str_pickle and _patch_capi_unicode_decode_as_bstr.
"""

from cpython cimport PyUnicode_Decode
from cpython cimport PyBytes_FromStringAndSize, _PyBytes_Resize

cdef extern from "Python.h":
    char* PyBytes_AS_STRING(PyObject*)
    Py_ssize_t PyBytes_GET_SIZE(PyObject*)

cdef extern from "Python.h":
    ctypedef PyObject* (*PyCFunction)(PyObject*, PyObject*)
    ctypedef struct PyMethodDef:
        const char* ml_name
        PyCFunction ml_meth
    ctypedef struct PyCFunctionObject:
        PyMethodDef *m_ml
        PyObject*    m_self
        PyObject*    m_module

cdef extern from "structmember.h":
    ctypedef struct PyMemberDef:
        const char* name
        int         type
        Py_ssize_t  offset

    enum:
        T_INT

from libc.stdlib cimport malloc, free
from libc.string cimport memcpy, memcmp

if PY_MAJOR_VERSION >= 3:
    import copyreg as pycopyreg
else:
    import copy_reg as pycopyreg

cdef object zbinary  # = zodbpickle.binary | None
try:
    import zodbpickle
except ImportError:
    zbinary = None
else:
    zbinary = zodbpickle.binary


# support for pickling bstr/ustr as standalone types.
#
# pickling is organized in such a way that
# - what is saved by py2 can be loaded correctly on both py2/py3,  and similarly
# - what is saved by py3 can be loaded correctly on both py2/py3   as well.
#
# XXX place
cdef _bstr__reduce_ex__(self, protocol):
    # Ideally we want to emit bstr(BYTES), but BYTES is not available for
    # protocol < 3. And for protocol < 3 emitting bstr(STRING) is not an
    # option because plain py3 raises UnicodeDecodeError on loading arbitrary
    # STRING data. However emitting bstr(UNICODE) works universally because
    # pickle supports arbitrary unicode - including invalid unicode - out of
    # the box and in exactly the same way on both py2 and py3. For the
    # reference upstream py3 uses surrogatepass on encode/decode UNICODE data
    # to achieve that.
    if protocol < 3:
        # use UNICODE for data
        udata = _udata(pyu(self))
        if protocol < 2:
            return (self.__class__, (udata,))   # bstr UNICODE REDUCE
        else:
            return (pycopyreg.__newobj__,
                    (self.__class__, udata))    # bstr UNICODE NEWOBJ
    else:
        # use BYTES for data
        bdata = _bdata(self)
        if PY_MAJOR_VERSION < 3:
            # the only way we can get here on py2 and protocol >= 3 is zodbpickle
            # -> similarly to py3 save bdata as BYTES
            assert zbinary is not None
            bdata = zbinary(bdata)
        return (
            pycopyreg.__newobj__,               # bstr BYTES   NEWOBJ
            (self.__class__, bdata))

cdef _ustr__reduce_ex__(self, protocol):
    # emit ustr(UNICODE).
    # TODO later we might want to switch to emitting ustr(BYTES)
    #      even if we do this, it should be backward compatible
    if protocol < 2:
        return (self.__class__, (_udata(self),))# ustr UNICODE REDUCE
    else:
        return (pycopyreg.__newobj__,           # ustr UNICODE NEWOBJ
                (self.__class__, _udata(self)))



# types used while patching
cdef extern from *:
    """
    struct PicklerObject;
    """
    struct PicklerObject:
        pass

cdef struct PicklerTypeInfo:
    Py_ssize_t size                 # sizeof(PicklerObject)
    Py_ssize_t off_bin              # offsetof `int bin`
    Py_ssize_t off_poutput_buffer   # offsetof `PyObject *output_buffer`
    Py_ssize_t off_output_len       # offsetof `Py_ssize_t output_len`
    Py_ssize_t off_max_output_len   # offsetof `Py_ssize_t max_output_len`


# XXX place ?
cdef extern from * nogil:
    r"""
    // CALLCONV instructs compiler to use specified builtin calling convention.
    // it should be used like this:
    //
    //  int CALLCONV(stdcall) myfunc(...)
    #ifndef LIBGOLANG_CC_msc
    # define CALLCONV(callconv) __attribute__((callconv))
    #else // MSC
    # define CALLCONV(callconv) __##callconv
    #endif


    // FOR_EACH_CALLCONV invokes macro X(ccname, callconv, cckind) for every supported calling convention.
    // cckind is one of `builtin` or `custom`.
    #ifdef LIBGOLANG_ARCH_386
    # ifndef LIBGOLANG_CC_msc
    #  define FOR_EACH_CALLCONV(X)  \
         X(default,,                            builtin)    \
         X(cdecl,       CALLCONV(cdecl),        builtin)    \
         X(stdcall,     CALLCONV(stdcall),      builtin)    \
         X(fastcall,    CALLCONV(fastcall),     builtin)    \
         X(thiscall,    CALLCONV(thiscall),     builtin)    \
         X(regparm1,    CALLCONV(regparm(1)),   builtin)    \
         X(regparm2,    CALLCONV(regparm(2)),   builtin)    \
         X(regparm3,    CALLCONV(regparm(3)),   builtin)    \
         X(fastcall_nostkclean,  na,            custom )
    # else // MSC
    #  define FOR_EACH_CALLCONV(X)  \
         X(default,,                            builtin)    \
         X(cdecl,       CALLCONV(cdecl),        builtin)    \
         X(stdcall,     CALLCONV(stdcall),      builtin)    \
         X(fastcall,    CALLCONV(fastcall),     builtin)    \
         /* X(CALLCONV(thiscall),   thiscall)   MSVC emits "C3865: '__thiscall': can only be used on native member functions"       */ \
         /* in theory we can emulate thiscall via fastcall https://tresp4sser.wordpress.com/2012/10/06/how-to-hook-thiscall-functions/ */ \
         X(vectorcall,  CALLCONV(vectorcall),   builtin)    \
         X(fastcall_nostkclean,  na,            custom )
    # endif
    #elif defined(LIBGOLANG_ARCH_amd64)
    # define FOR_EACH_CALLCONV(X)   \
        X(default,,                             builtin)
    #elif defined(LIBGOLANG_ARCH_arm64)
    # define FOR_EACH_CALLCONV(X)   \
        X(default,,             builtin)
    #else
    # error "unsupported architecture"
    #endif

    // Callconv denotes calling convention of a function.
    enum Callconv {
    #define CC_ENUM1(ccname, _, __) \
        CALLCONV_##ccname,
    FOR_EACH_CALLCONV(CC_ENUM1)
    };

    const char* callconv_str(Callconv cconv) {
        using namespace golang;
        switch(cconv) {
        #define CC_STR1(ccname, _, __)  \
        case CALLCONV_##ccname:       \
            return #ccname;
        FOR_EACH_CALLCONV(CC_STR1)
        default:
            panic("bug");
        }
    }

    // SaveFunc represents a save function - its address and calling convention.
    struct SaveFunc {
        void*     addr;
        Callconv  cconv;
    };
    """
    enum Callconv: pass
    const char* callconv_str(Callconv)
    struct SaveFunc:
        void*    addr
        Callconv cconv

# XXX doc
cdef struct _pickle_PatchCtx:
    initproc Unpickler_tp_xinit             # func to replace Unpickler.tp_init
    initproc Unpickler_tp_init_orig         # what was there before

    vector[SaveFunc]  Pickler_xsave_ccv     # func to replace _Pickler_save  (all callconv variants)
    SaveFunc          Pickler_save_orig     # what was there before

    PicklerTypeInfo iPickler                # information detected about PicklerObject type


# patch contexts for _pickle and _zodbpickle modules
cdef _pickle_PatchCtx _pickle_patchctx
cdef _pickle_PatchCtx _zpickle_patchctx


# _patch_str_pickle patches *pickle modules to support bstr/ustr and UTF-8 properly.
#
# STRING opcodes are handled in backward-compatible way:
#
# - *STRING are loaded as bstr
# - bstr is saved as *STRING
# - pickletools decodes *STRING as UTF-8
cdef _patch_str_pickle():
    try:
        import zodbpickle
    except ImportError:
        zodbpickle = None

    # py3: pickletools.dis raises UnicodeDecodeError on non-ascii STRING and treats *BINSTRING as latin1
    #      -> decode as UTF8b instead
    if PY_MAJOR_VERSION >= 3:
        import pickletools, codecs
        _codecs_escape_decode = codecs.escape_decode
        def xread_stringnl(f):
            data = _codecs_escape_decode(pickletools.read_stringnl(f, decode=False))[0]
            return pybstr(data)
        def xread_string1(f):
            data = pickletools.read_string1(f).encode('latin1')
            return pybstr(data)
        def xread_string4(f):
            data = pickletools.read_string4(f).encode('latin1')
            return pybstr(data)

        pickletools.stringnl.reader = xread_stringnl
        pickletools.string1.reader  = xread_string1
        pickletools.string4.reader  = xread_string4

        if zodbpickle:
            from zodbpickle import pickletools_3 as zpickletools
            zpickletools.stringnl.reader = xread_stringnl   # was same logic as in std pickletools
            zpickletools.string1.reader  = xread_string1
            zpickletools.string4.reader  = xread_string4

    # py3: pickle.load wants to treat *STRING as bytes and decode it as ASCII
    #      -> adjust to decode to bstr instead
    #      -> also save bstr via *STRING opcodes so that load/save is identity
        import pickle, _pickle
        # TODO _pickle not available (pypy)
        _pickle_patchctx.Unpickler_tp_xinit = _pickle_Unpickler_xinit
        _pickle_patchctx.Pickler_xsave_ccv  = _pickle_Pickler_xsave_ccv
        _patch_pickle(pickle, _pickle, &_pickle_patchctx)

        if zodbpickle:
            from zodbpickle import pickle as zpickle, _pickle as _zpickle
            from zodbpickle import slowpickle as zslowPickle, fastpickle as zfastPickle
            # TODO _pickle / fastpickle not available (pypy)
            for x in 'load', 'loads', 'Unpickler', 'dump', 'dumps', 'Pickler':
                assert getattr(_zpickle, x) is getattr(zfastPickle, x)
                assert getattr(zpickle, x)  is getattr(_zpickle, x)
            _patch_pickle(zslowPickle, None, NULL)
            _zpickle_patchctx.Unpickler_tp_xinit = _zpickle_Unpickler_xinit
            _zpickle_patchctx.Pickler_xsave_ccv  = _zpickle_Pickler_xsave_ccv
            _patch_pickle(None, zfastPickle, &_zpickle_patchctx)
            # propagate changes from fastpickle -> _zpickle -> zpickle
            _zpickle.load  = zfastPickle.load
            _zpickle.loads = zfastPickle.loads
            _zpickle.dump  = zfastPickle.dump
            _zpickle.dumps = zfastPickle.dumps
            assert _zpickle.Unpickler is zfastPickle.Unpickler
            assert _zpickle.Pickler   is zfastPickle.Pickler
            zpickle.load   = zfastPickle.load
            zpickle.loads  = zfastPickle.loads
            zpickle.dump   = zfastPickle.dump
            zpickle.dumps  = zfastPickle.dumps
            assert zpickle.Unpickler  is zfastPickle.Unpickler
            assert zpickle.Pickler    is zfastPickle.Pickler

# _patch_pickle serves _patch_str_pickle by patching pair of py-by-default and
# C implementations of a pickle module.
#
# pickle or _pickle being None indicates that corresponding module version is not available.
cdef _patch_pickle(pickle, _pickle, _pickle_PatchCtx* _pctx):
    # if C module is available - it should shadow default py implementation
    if _pickle is not None  and  pickle is not None:
        assert pickle.load      is  _pickle.load
        assert pickle.loads     is  _pickle.loads
        assert pickle.Unpickler is  _pickle.Unpickler
        assert pickle.dump      is  _pickle.dump
        assert pickle.dumps     is  _pickle.dumps
        assert pickle.Pickler   is  _pickle.Pickler

    # patch C
    if _pickle is not None:
        _patch_cpickle(_pickle, _pctx)
        # propagate C updates to py
        if pickle is not None:
            pickle.load      = _pickle.load
            pickle.loads     = _pickle.loads
            pickle.Unpickler = _pickle.Unpickler
            pickle.dump      = _pickle.dump
            pickle.dumps     = _pickle.dumps        # XXX needed?
            pickle.Pickler   = _pickle.Pickler

    # patch py
    if pickle is not None:
        _patch_pypickle(pickle, shadowed = (_pickle is not None))

# _patch_pypickle serves _patch_pickle for py version.
cdef _patch_pypickle(pickle, shadowed):
    def pyattr(name):
        if shadowed:
            name = '_'+name
        return getattr(pickle, name)

    # adjust load / loads / Unpickler to use 'bstr' encoding by default
    Unpickler = pyattr('Unpickler')
    for f in pyattr('load'), pyattr('loads'), Unpickler.__init__:
        f.__kwdefaults__['encoding'] = 'bstr'

    # patch Unpickler._decode_string to handle 'bstr' encoding
    # zodbpickle uses .decode_string from first version of patch from bugs.python.org/issue6784
    has__decode = hasattr(Unpickler, '_decode_string')
    has_decode  = hasattr(Unpickler, 'decode_string')
    assert has__decode or has_decode
    assert not (has__decode and has_decode)
    _decode_string = '_decode_string'  if has__decode  else  'decode_string'

    Unpickler_decode_string = getattr(Unpickler, _decode_string)
    def _xdecode_string(self, value):
        if self.encoding == 'bstr':
            return pyb(value)
        else:
            return Unpickler_decode_string(self, value)
    setattr(Unpickler, _decode_string, _xdecode_string)

    # adjust Pickler to save bstr as STRING
    from struct import pack
    Pickler = pyattr('Pickler')
    def save_bstr(self, obj):
        cdef bint nonascii_escape  # unused
        if self.proto >= 1:
            n = len(obj)
            if n < 256:
                op = b'U' + bytes((n,)) + _bdata(obj)   # SHORT_BINSTRING
            else:
                op = b'T' + pack('<i', n) + _bdata(obj) # BINSTRING
        else:
            qobj = strconv._quote(obj, b"'", &nonascii_escape)
            op = b'S' + qobj + b'\n'                    # STRING
        self.write(op)
        self.memoize(obj)
    Pickler.dispatch[pybstr] = save_bstr

# _patch_cpickle serves _patch_pickle for C version.
cdef _patch_cpickle(_pickle, _pickle_PatchCtx *pctx):
    # adjust load / loads to use 'bstr' encoding by default
    # builtin_function_or_method does not have __kwdefaults__  (defaults for
    # arguments are hardcoded in generated C code)
    # -> wrap functions
    _pickle_load  = _pickle.load
    _pickle_loads = _pickle.loads
    def load (file,    *, **kw):
        kw.setdefault('encoding', 'bstr')
        return _pickle_load (file, **kw)
    def loads(data,    *, **kw):
        kw.setdefault('encoding', 'bstr')
        return _pickle_loads(data, **kw)
    _pickle.load  = load
    _pickle.loads = loads

    # adjust Unpickler to use 'bstr' encoding by default
    assert isinstance(_pickle.Unpickler, type)
    cdef _XPyTypeObject* Unpickler = <_XPyTypeObject*>(_pickle.Unpickler)

    pctx.Unpickler_tp_init_orig = Unpickler.tp_init
    Unpickler.tp_init = pctx.Unpickler_tp_xinit

    def Unpickler_x__init__(self, *argv, **kw):
        # NOTE don't return - just call: __init__ should return None
        pctx.Unpickler_tp_xinit(self, <PyObject*>argv, <PyObject*>kw)

    _patch_slot(<PyTypeObject*>Unpickler, '__init__', Unpickler_x__init__)
    # decoding to bstr relies on _patch_capi_unicode_decode_as_bstr

    # adjust Pickler to save bstr as *STRING
    # it is a bit involved because:
    # - save function, that we need to patch, is not exported.
    # - _Pickle_Write, that we need to use from patched save, is not exported neither.
    pctx.iPickler = _detect_Pickler_typeinfo(_pickle.Pickler)
    pctx.Pickler_save_orig = save = _find_Pickler_save(_pickle.Pickler)
    xsave = pctx.Pickler_xsave_ccv[save.cconv]
    assert xsave.cconv == save.cconv, (callconv_str(xsave.cconv), callconv_str(save.cconv))
    cpatch(&pctx.Pickler_save_orig.addr, xsave.addr)

    # XXX test at runtime that we hooked save correctly


# ---- adjusted C bits for loading ----

# adjust Unpickler to use 'bstr' encoding by default and handle that encoding
# in PyUnicode_Decode by returning bstr instead of unicode. This mirrors
# corresponding py loading adjustments.

cdef int _pickle_Unpickler_xinit(object self, PyObject* args, PyObject* kw) except -1:
    xkw = {'encoding': 'bstr'}
    if kw != NULL:
        xkw.update(<object>kw)
    return _pickle_patchctx.Unpickler_tp_init_orig(self, args, <PyObject*>xkw)

cdef int _zpickle_Unpickler_xinit(object self, PyObject* args, PyObject* kw) except -1:
    xkw = {'encoding': 'bstr'}
    if kw != NULL:
        xkw.update(<object>kw)
    return _zpickle_patchctx.Unpickler_tp_init_orig(self, args, <PyObject*>xkw)

ctypedef object unicode_decodefunc(const char*, Py_ssize_t, const char* encoding, const char* errors)
cdef unicode_decodefunc* _punicode_Decode
cdef object _unicode_xDecode(const char *s, Py_ssize_t size, const char* encoding, const char* errors):
    if encoding != NULL  and  strcmp(encoding, 'bstr') == 0:
        bobj = PyBytes_FromStringAndSize(s, size)  # TODO -> PyBSTR_FromStringAndSize directly
        return pyb(bobj)
    return _punicode_Decode(s, size, encoding, errors)

cdef _patch_capi_unicode_decode_as_bstr():
    global _punicode_Decode
    _punicode_Decode = PyUnicode_Decode
    cpatch(<void**>&_punicode_Decode, <void*>_unicode_xDecode)


# ---- adjusted C bits for saving ----

# adjust Pickler save to save bstr via *STRING opcodes.
# This mirrors corresponding py saving adjustments, but is more involved to implement.

cdef int _pickle_Pickler_xsave(PicklerObject* self, PyObject* obj, int pers_save) except -1:
    return __Pickler_xsave(&_pickle_patchctx, self, obj, pers_save)

cdef int _zpickle_Pickler_xsave(PicklerObject* self, PyObject* obj, int pers_save) except -1:
    return __Pickler_xsave(&_zpickle_patchctx, self, obj, pers_save)

# callconv wrappers XXX place
cdef extern from *:
    r"""
    static int __pyx_f_6golang_7_golang__pickle_Pickler_xsave(PicklerObject*, PyObject*, int);
    static int __pyx_f_6golang_7_golang__zpickle_Pickler_xsave(PicklerObject*, PyObject*, int);

    #define DEF_PICKLE_XSAVE_builtin(ccname, callconv)                                      \
    static int callconv                                                                     \
    _pickle_Pickler_xsave_##ccname(PicklerObject* self, PyObject* obj, int pers_save) {     \
        return __pyx_f_6golang_7_golang__pickle_Pickler_xsave(self, obj, pers_save);        \
    }
    #define DEF_ZPICKLE_XSAVE_builtin(ccname, callconv)                                     \
    static int callconv                                                                     \
    _zpickle_Pickler_xsave_##ccname(PicklerObject* self, PyObject* obj, int pers_save) {    \
        return __pyx_f_6golang_7_golang__zpickle_Pickler_xsave(self, obj, pers_save);       \
    }

    #define DEF_PICKLE_XSAVE_custom(ccname, _)                                              \
        extern "C" char _pickle_Pickler_xsave_##ccname;
    #define DEF_ZPICKLE_XSAVE_custom(ccname, _)                                             \
        extern "C" char _zpickle_Pickler_xsave_##ccname;

    #define DEF_PICKLE_XSAVE(ccname, callconv, cckind)  DEF_PICKLE_XSAVE_##cckind(ccname, callconv)
    #define DEF_ZPICKLE_XSAVE(ccname, callconv, cckind) DEF_ZPICKLE_XSAVE_##cckind(ccname, callconv)

    FOR_EACH_CALLCONV(DEF_PICKLE_XSAVE)
    FOR_EACH_CALLCONV(DEF_ZPICKLE_XSAVE)

    static std::vector<SaveFunc> _pickle_Pickler_xsave_ccv = {
    #define PICKLE_CC_XSAVE(ccname, _, __)  \
        SaveFunc{(void*)&_pickle_Pickler_xsave_##ccname, CALLCONV_##ccname},
    FOR_EACH_CALLCONV(PICKLE_CC_XSAVE)
    };

    static std::vector<SaveFunc> _zpickle_Pickler_xsave_ccv = {
    #define ZPICKLE_CC_XSAVE(ccname, _, __) \
        SaveFunc{(void*)&_zpickle_Pickler_xsave_##ccname, CALLCONV_##ccname},
    FOR_EACH_CALLCONV(ZPICKLE_CC_XSAVE)
    };

    // proxy for asm routines to invoke _pickle_Pickler_xsave and _zpickle_Pickler_xsave
    #ifdef LIBGOLANG_ARCH_386
    extern "C" int CALLCONV(fastcall)
    _pickle_Pickler_xsave_ifastcall(PicklerObject* self, PyObject* obj, int pers_save) {
        return __pyx_f_6golang_7_golang__pickle_Pickler_xsave(self, obj, pers_save);
    }
    extern "C" int CALLCONV(fastcall)
    _zpickle_Pickler_xsave_ifastcall(PicklerObject* self, PyObject* obj, int pers_save) {
        return __pyx_f_6golang_7_golang__zpickle_Pickler_xsave(self, obj, pers_save);
    }
    #endif
    """
    vector[SaveFunc] _pickle_Pickler_xsave_ccv
    vector[SaveFunc] _zpickle_Pickler_xsave_ccv


cdef int __Pickler_xsave(_pickle_PatchCtx* pctx, PicklerObject* self, PyObject* obj, int pers_save) except -1:
    # !bstr -> use builtin pickle code
    if obj.ob_type != <PyTypeObject*>pybstr:
        return save_invoke(pctx.Pickler_save_orig.addr, pctx.Pickler_save_orig.cconv,
                                self, obj, pers_save)

    # bstr  -> pickle it as *STRING
    cdef const char* s
    cdef Py_ssize_t  l
    cdef byte[5]     h
    cdef Py_ssize_t  lh = 1;
    cdef bint nonascii_escape

    cdef int bin = (<int*>((<byte*>self) + pctx.iPickler.off_bin))[0]
    if bin == 0:
        esc = strconv._quote(<object>obj, "'", &nonascii_escape)
        assert type(esc) is bytes
        s = PyBytes_AS_STRING(<PyObject*>esc)
        l = PyBytes_GET_SIZE(<PyObject*>esc)
        __Pickler_xWrite(pctx, self, b'S', 1)   # STRING
        __Pickler_xWrite(pctx, self, s, l)
        __Pickler_xWrite(pctx, self, b'\n', 1)

    else:
        s = PyBytes_AS_STRING(obj)
        l = PyBytes_GET_SIZE(obj)
        if l < 0x100:
            h[0] = b'U'     # SHORT_BINSTRING
            h[1] = <byte>l
            lh += 1
        elif l < 0x7fffffff:
            h[0] = b'T'     # BINSTRING
            h[1] = <byte>(l >> 0)
            h[2] = <byte>(l >> 8)
            h[3] = <byte>(l >> 16)
            h[4] = <byte>(l >> 24)
            lh += 4
        else:
            raise OverflowError("cannot serialize a string larger than 2 GiB")

        __Pickler_xWrite(pctx, self, <char*>h, lh)
        __Pickler_xWrite(pctx, self, s, l)

    return 0


# __Pickler_xWrite mimics original _Pickler_Write.
#
# we have to implement it ourselves because there is no way to discover
# original _Pickler_Write address: contrary to `save` function _Pickler_Write
# is small and is not recursive. A compiler is thus free to create many
# versions of it with e.g. constant propagation and to inline it freely. The
# latter actually happens for real on LLVM which for py3.11 inlines
# _Pickler_Write fully without leaving any single freestanding instance of it.
#
# XXX explain why we can skip flush in zpickle case
# XXX explain that we do not emit FRAME
cdef int __Pickler_xWrite(_pickle_PatchCtx* pctx, PicklerObject* self, const char* s, Py_ssize_t l) except -1:
    ppoutput_buffer = <PyObject**> (<byte*>self + pctx.iPickler.off_poutput_buffer)
    poutput_len     = <Py_ssize_t*>(<byte*>self + pctx.iPickler.off_output_len)
    pmax_output_len = <Py_ssize_t*>(<byte*>self + pctx.iPickler.off_max_output_len)

    assert ppoutput_buffer[0].ob_type == &PyBytes_Type
    assert l >= 0
    assert poutput_len[0] >= 0

    if l > PY_SSIZE_T_MAX - poutput_len[0]:
        raise MemoryError() # overflow

    need = poutput_len[0] + l
    if need > pmax_output_len[0]:
        if need >= PY_SSIZE_T_MAX // 2:
            raise MemoryError()
        pmax_output_len[0] = need // 2 * 3
        _PyBytes_Resize(ppoutput_buffer, pmax_output_len[0])

    buf = PyBytes_AS_STRING(ppoutput_buffer[0])
    memcpy(buf + poutput_len[0], s, l)
    poutput_len[0] += l

    return 0


# ---- infrastructure to assist patching C saving codepath ----

# _detect_Pickler_typeinfo detects information about PicklerObject type
# through runtime introspection.
#
# This information is used mainly by __Pickler_xWrite.
cdef PicklerTypeInfo _detect_Pickler_typeinfo(pyPickler) except *:
    cdef PicklerTypeInfo t

    cdef bint debug = False
    def trace(*argv):
        if debug:
            print(*argv)
    trace()

    assert isinstance(pyPickler, type)
    cdef PyTypeObject*   Pickler  = <PyTypeObject*>   pyPickler
    cdef _XPyTypeObject* xPickler = <_XPyTypeObject*> pyPickler

    # sizeof
    assert Pickler.tp_basicsize  > 0
    assert Pickler.tp_itemsize  == 0
    t.size = Pickler.tp_basicsize
    trace('size:\t', t.size)

    # busy keeps offsets of all bytes for already detected fields
    busy = set()
    def markbusy(off, size):
        for _ in range(off, off+size):
            assert _ not in busy,  (_, busy)
            assert 0 < off <= t.size
            busy.add(_)

    # .bin
    cdef PyMemberDef* mbin = tp_members_lookup(xPickler.tp_members, 'bin')
    assert mbin.type == T_INT, (mbin.type,)
    t.off_bin = mbin.offset
    markbusy(t.off_bin, sizeof(int))
    trace('.bin:\t', t.off_bin)

    # .output_buffer
    #
    #   1) new Pickler
    #   2) .memo = {}    - the only pointer that changes is .memo (PyMemoTable* - not pyobject)
    #   3) .tp_clear()   - all changed words are changed to 0 and cover non-optional PyObject* and memo
    #   4) .__init__()
    #   5) go through offsets of all pyobjects and find the one with .ob_type = PyBytes_Type
    #      -> that is .output_buffer

    #       1)
    class Null:
        def write(self, data): pass
    pyobj = pyPickler(Null())
    cdef PyObject* obj = <PyObject*>pyobj
    assert obj.ob_type == Pickler

    cdef byte* bobj  = <byte*>obj
    cdef byte* bobj2 = <byte*>malloc(t.size)
    # obj_copy copies obj to obj2.
    def obj_copy():
        memcpy(bobj2, bobj, t.size)
    # obj_diff finds difference in between obj2 and obj.
    def obj_diff(Py_ssize_t elemsize): # -> []offset
        assert (elemsize & (elemsize - 1)) == 0,  elemsize # elemsize is 2^x
        cdef Py_ssize_t off

        # skip PyObject_HEAD
        off = sizeof(PyObject)
        off = (off + elemsize - 1) & (~(elemsize - 1))
        assert off % elemsize == 0

        # find out offsets of different elements
        vdelta = []
        while off + elemsize <= t.size:
            if memcmp(bobj + off, bobj2 + off, elemsize):
                vdelta.append(off)
            off += elemsize

        return vdelta

    #       2)
    obj_copy()
    pyobj.memo = {}
    dmemo = obj_diff(sizeof(void*))
    assert len(dmemo) == 1,  dmemo
    off_memo = dmemo[0]
    markbusy(off_memo, sizeof(void*))
    trace('.memo:\t', off_memo)

    #       3)
    assert Pickler.tp_clear != NULL
    obj_copy()
    Pickler.tp_clear(pyobj)
    pointers = obj_diff(sizeof(void*))
    for poff in pointers:
        assert (<void**>(bobj + <Py_ssize_t>poff))[0] == NULL
    assert off_memo in pointers
    pyobjects = pointers[:]
    pyobjects.remove(off_memo)
    trace('pyobjects:\t', pyobjects)

    #       4)
    pyobj.__init__(Null())

    #       5)
    cdef PyObject* bout = NULL
    t.off_poutput_buffer = 0
    for poff in pyobjects:
        x = (<PyObject**>(bobj + <Py_ssize_t>poff))[0]
        if x.ob_type == &PyBytes_Type:
            if t.off_poutput_buffer == 0:
                t.off_poutput_buffer = poff
            else:
                raise AssertionError("found several <bytes> inside Pickler")
    assert t.off_poutput_buffer != 0
    markbusy(t.off_poutput_buffer, sizeof(PyObject*))
    trace(".output_buffer:\t", t.off_poutput_buffer)

    # .output_len  +  .max_output_len
    # dump something small and expected -> find out which field changes correspondingly
    import io
    output_len     = None
    max_output_len = None
    for n in range(1,10):
        f = io.BytesIO()
        pyobj.__init__(f, 0)
        o = (None,)*n
        pyobj.dump(o)
        p = f.getvalue()
        phok = b'(' + b'N'*n + b't'  # full trails with "p0\n." but "p0\n" is optional
        assert p.startswith(phok), p

        # InspectWhilePickling observes obj while the pickling is going on:
        # - sees which fields have changes
        # - sees which fields are candidates for max_output_len
        class InspectWhilePickling:
            def __init__(self):
                self.diff     = None  # what changes
                self.doff2val = {}    # off from .diff  ->  Py_ssize_t read from it
                self.max_output_len = set() # offsets that are candidates for .max_output_len

            def __reduce__(self):
                self.diff = obj_diff(sizeof(Py_ssize_t))
                for off in self.diff:
                    self.doff2val[off] = (<Py_ssize_t*>(bobj + <Py_ssize_t>off))[0]

                cdef PyObject* output_buffer = \
                        (<PyObject**>(bobj + t.off_poutput_buffer))[0]
                assert output_buffer.ob_type == &PyBytes_Type
                off = sizeof(PyObject)
                off = (off + sizeof(Py_ssize_t) - 1) & (~(sizeof(Py_ssize_t) - 1))
                assert off % sizeof(Py_ssize_t) == 0
                while off + sizeof(Py_ssize_t) <= t.size:
                    v = (<Py_ssize_t*>(bobj + <Py_ssize_t>off))[0]
                    if v == PyBytes_GET_SIZE(output_buffer):
                        self.max_output_len.add(off)
                    off += sizeof(Py_ssize_t)

                return (int, ())    # arbitrary

        pyobj.__init__(Null(), 0)
        i = InspectWhilePickling()
        o += (i,)
        obj_copy()
        pyobj.dump(o)
        assert i.diff is not None
        #trace('n%d  diff: %r\toff2val: %r' % (n, i.diff, i.doff2val))
        #trace('     ', busy)

        noutput_len = set()
        for off in i.diff:
            if off not in busy:
                if i.doff2val[off] == (len(phok)-1): # (NNNN without t yet
                    noutput_len.add(off)
        assert len(noutput_len) >= 1, noutput_len
        if output_len is None:
            output_len = noutput_len
        else:
            output_len.intersection_update(noutput_len)

        nmax_output_len = set()
        for off in i.max_output_len:
            if off not in busy:
                nmax_output_len.add(off)
        assert len(nmax_output_len) >= 1, nmax_output_len
        if max_output_len is None:
            max_output_len = nmax_output_len
        else:
            max_output_len.intersection_update(nmax_output_len)

    if len(output_len) != 1:
        raise AssertionError("cannot find .output_len")
    if len(max_output_len) != 1:
        raise AssertionError("cannot find .max_output_len")

    t.off_output_len = output_len.pop()
    markbusy(t.off_output_len, sizeof(Py_ssize_t))
    trace(".output_len:\t", t.off_output_len)

    t.off_max_output_len = max_output_len.pop()
    markbusy(t.off_max_output_len, sizeof(Py_ssize_t))
    trace(".max_output_len:\t", t.off_max_output_len)

    free(bobj2)
    return t


# _find_Pickler_save determines address and calling convention of `save` C
# function associated with specified Pickler.
#
# Address and calling convention of `save` are needed to be able to patch it.
cdef SaveFunc _find_Pickler_save(pyPickler) except *:
    cdef SaveFunc save
    save.addr  = __find_Pickler_save(pyPickler)
    save.cconv = __detect_save_callconv(pyPickler, save.addr)
    #fprintf(stderr, "save.addr:  %p\n", save.addr)
    #fprintf(stderr, "save.cconv: %s\n", callconv_str(save.cconv))
    return save

cdef void* __find_Pickler_save(pyPickler) except NULL:
    assert isinstance(pyPickler, type)

    # start from _pickle_Pickler_dump as root and analyze how called functions
    # behave wrt pickling deep chain of objects. We know whether a callee leads
    # to save if, upon receiving control in our __reduce__, we see that the
    # callee was entered and did not exited yet. If we find such a callee, we
    # recourse the process and start to analyze functions that the callee invokes
    # itself. We detect reaching save when we see that a callee was entered
    # many times recursively. That happens because we feed deep recursive
    # structure to the pickle, and because save itself is organized to invoke
    # itself recursively - e.g. (obj,) is pickled via save -> save_tuple -> save.
    cdef _XPyTypeObject* Pickler = <_XPyTypeObject*>(pyPickler)
    cdef PyMethodDef*    mdump   = tp_methods_lookup(Pickler.tp_methods, 'dump')
    #print("%s _pickle_Pickler_dump:" % pyPickler)
    addr = <void*>mdump.ml_meth  # = _pickle_Pickler_dump
    while 1:
        vcallee = cfunc_direct_callees(addr)
        ok = False
        for i in range(vcallee.size()):
            callee = vcallee[i]
            #fprintf(stderr, "checking %p ...\n", callee)
            nentry = _nentry_on_deep_save(pyPickler, callee)
            #fprintf(stderr, "%p  - %ld\n", callee, nentry)
            assert nentry in (0, 1)  or  nentry > 5,  nentry
            if nentry > 5:
                return callee   # found save
            if nentry == 1:
                addr = callee   # found path that will lead to save
                ok = True
                break

        if not ok:
            raise AssertionError('cannot find path leading to save')

# _nentry_on_deep_save tests how addr is related to `save` via inspecting
# addr entry count when Pickler is feed deep recursive structure.
#
# if #entry is 0   - addr is unrelated to save
# if #entry is 1   - addr is related to save and calls it
# if #entry is big - addr is save
cdef long _nentry_on_deep_save(pyPickler, void* addr) except -1: # -> nentry
    # below we rely on inside_counted which alters return address during the
    # call to wrapped func. In practice this does not create problems on x86_64
    # and arm64, but on i386 there are many calls to functions like
    # x86.get_pc_thunk.ax which are used to implement PC-relative addressing.
    # If we let inside_counted to hook such a func it will result in a crash
    # because returned address will be different from real PC of the caller.
    # Try to protect us from entering into such situation by detecting leaf
    # functions and not hooking them. For the reference x86.get_pc_thunk.ax is:
    #
    #       movl (%esp), %eax
    #       ret
    vcallee = cfunc_direct_callees(addr)
    if vcallee.size() == 0:
        return 0

    # InspectWhilePickling observes how many times currently considered
    # function was entered at the point of deep recursion inside save.
    class InspectWhilePickling:
        def __init__(self):
            self.inside_counter = None
        def __reduce__(self):
            self.inside_counter = inside_counter
            return (int, ())    # arbitrary

    class Null:
        def write(self, data): pass

    i = InspectWhilePickling()
    obj = (i,)
    for _ in range(20):
        obj = (obj,)

    p = pyPickler(Null(), 0)

    h = xfunchook_create()
    global inside_counted_func
    inside_counted_func = addr
    xfunchook_prepare(h, &inside_counted_func, <void*>inside_counted)
    xfunchook_install(h, 0)
    p.dump(obj)
    xfunchook_uninstall(h, 0)
    xfunchook_destroy(h)

    assert i.inside_counter is not None
    return i.inside_counter


# inside_counted is used to patch a function to count how many times that
# function is entered/leaved.
cdef extern from * nogil: # see _golang_str_pickle.S for details
    """
    extern "C" {
         extern void  inside_counted();
         extern void* inside_counted_func;
         extern long  inside_counter;
    }
    """
    void  inside_counted()
    void* inside_counted_func
    long  inside_counter


# __detect_save_callconv determines calling convention that compiler used for save.
#
# On architectures with many registers - e.g. x86_64 and arm64 - the calling
# convention is usually the same as default, but on e.g. i386 - where the
# default cdecl means to put arguments on the stack, the compiler usually
# changes calling convention to use registers instead.
cdef Callconv __detect_save_callconv(pyPickler, void* save) except *:
    for p in saveprobe_test_ccv:
        #print("save: probing %s" % callconv_str(p.cconv))
        good = __save_probe1(pyPickler, save, p.addr)
        #print("  ->", good)
        if good:
            return p.cconv
    bad = "cannot determine save calling convention\n\n"
    bad += "probed:\n"
    for p in saveprobe_test_ccv:
        bad += "  - %s\t; callee_stkcleanup: %d\n" % (callconv_str(p.cconv), cfunc_is_callee_cleanup(p.addr))
    bad += "\n"
    bad += "save callee_stkcleanup: %d\n" % cfunc_is_callee_cleanup(save)
    bad += "save disassembly:\n%s" % cfunc_disasm(save)
    raise AssertionError(bad)

cdef bint __save_probe1(pyPickler, void* save, void* cfunc) except *:
    # first see whether stack is cleaned up by caller or callee and how much.
    # we need to do this first to avoid segfault if we patch save with cfunc
    # with different stack cleanup as the probe.
    save_stkclean  = cfunc_is_callee_cleanup(save)
    cfunc_stkclean = cfunc_is_callee_cleanup(cfunc)
    if save_stkclean != cfunc_stkclean:
        return False

    # now when we know that save and cfunc have the same stack cleanup protocol, we can start probing
    global saveprobe_ncall, saveprobe_self, saveprobe_obj, saveprobe_pers_save
    saveprobe_ncall = 0
    saveprobe_self  = NULL
    saveprobe_obj   = NULL
    saveprobe_pers_save = 0xdeafbeaf

    class Null:
        def write(self, data): pass
    p = pyPickler(Null(), 0)
    obj = object()

    h = xfunchook_create()
    xfunchook_prepare(h, &save, cfunc)
    xfunchook_install(h, 0)
    p.dump(obj)
    xfunchook_uninstall(h, 0)
    xfunchook_destroy(h)

    assert saveprobe_ncall == 1, saveprobe_ncall
    good = (saveprobe_self == <void*>p    and \
            saveprobe_obj  == <void*>obj  and \
            saveprobe_pers_save == 0)
    return good

cdef extern from * nogil:
    r"""
    static int    saveprobe_ncall;
    static void*  saveprobe_self;
    static void*  saveprobe_obj;
    static int    saveprobe_pers_save;

    static int saveprobe(void* self, PyObject* obj, int pers_save) {
        saveprobe_ncall++;
        saveprobe_self = self;
        saveprobe_obj  = obj;
        saveprobe_pers_save = pers_save;
        return 0; // do nothing
    }

    #define DEF_SAVEPROBE_builtin(ccname, callconv)                     \
        static int callconv                                             \
        saveprobe_##ccname(void* self, PyObject* obj, int pers_save) {  \
            return saveprobe(self, obj, pers_save);                     \
        }
    #define DEF_SAVEPROBE_custom(ccname, _)                             \
        extern "C" char saveprobe_##ccname;
    #define DEF_SAVEPROBE(ccname, callconv, cckind) DEF_SAVEPROBE_##cckind(ccname, callconv)
    FOR_EACH_CALLCONV(DEF_SAVEPROBE)

    static std::vector<SaveFunc> saveprobe_test_ccv = {
    #define CC_SAVEPROBE(ccname, _, __) \
        SaveFunc{(void*)&saveprobe_##ccname, CALLCONV_##ccname},
    FOR_EACH_CALLCONV(CC_SAVEPROBE)
    };

    // proxy for asm routines to invoke saveprobe
    #ifdef LIBGOLANG_ARCH_386
    extern "C" int CALLCONV(fastcall)
    saveprobe_ifastcall(void* self, PyObject* obj, int pers_save) { \
        return saveprobe(self, obj, pers_save);                     \
    }
    #endif
    """
    int   saveprobe_ncall
    void* saveprobe_self
    void* saveprobe_obj
    int   saveprobe_pers_save

    vector[SaveFunc] saveprobe_test_ccv


# XXX doc save_invoke ...
# XXX place
cdef extern from *:
    r"""
    #define CC_SAVE_DEFCALL1_builtin(ccname, callconv)
    #define CC_SAVE_DEFCALL1_custom(ccname, _)  \
        extern "C" int CALLCONV(fastcall)       \
        save_invoke_as_##ccname(void* save, void* self, PyObject* obj, int pers_save);
    #define CC_SAVE_DEFCALL1(ccname, callconv, cckind)  CC_SAVE_DEFCALL1_##cckind(ccname, callconv)
    FOR_EACH_CALLCONV(CC_SAVE_DEFCALL1)

    static int save_invoke(void* save, Callconv cconv, void* self, PyObject* obj, int pers_save) {
        using namespace golang;

        switch(cconv) {
    #define CC_SAVE_CALL1_builtin(ccname, callconv)     \
        case CALLCONV_ ## ccname:                                   \
            return ((int (callconv *)(void*, PyObject*, int))save)  \
                    (self, obj, pers_save);
    #define CC_SAVE_CALL1_custom(ccname, _)             \
        case CALLCONV_ ## ccname:                                   \
            return save_invoke_as_##ccname(save, self, obj, pers_save);
    #define CC_SAVE_CALL1(ccname, callconv, cckind) CC_SAVE_CALL1_##cckind(ccname, callconv)
    FOR_EACH_CALLCONV(CC_SAVE_CALL1)
        default:
            panic("unreachable");
        }
    }
    """
    int save_invoke(void* save, Callconv cconv, void* self, PyObject* obj, int pers_save) except -1


# - cfunc_direct_callees returns addresses of functions that cfunc calls directly.
#
# - cfunc_is_callee_cleanup determines whether cfunc does stack cleanup by
#   itself and for how much.
#
# - cfunc_disassembly returns disassembly of cfunc.
#
# XXX dedup iterating instructions -> DisasmIter
cdef extern from "capstone/capstone.h" nogil:
    r"""
    #include <algorithm>
    #include "golang/fmt.h"

    #if defined(LIBGOLANG_ARCH_amd64)
    # define MY_ARCH    CS_ARCH_X86
    # define MY_MODE    CS_MODE_64
    #elif defined(LIBGOLANG_ARCH_386)
    # define MY_ARCH    CS_ARCH_X86
    # define MY_MODE    CS_MODE_32
    #elif defined(LIBGOLANG_ARCH_arm64)
    # define MY_ARCH    CS_ARCH_ARM64
    # define MY_MODE    CS_MODE_LITTLE_ENDIAN
    #else
    # error "unsupported architecture"
    #endif

    static std::tuple<uint64_t, bool> _insn_getimm1(cs_arch arch, cs_insn* ins);
    std::vector<void*> cfunc_direct_callees(void *cfunc) {
        const bool debug = false;

        using namespace golang;
        using std::tie;
        using std::max;

        std::vector<void*> vcallee;

        csh       h;
        cs_insn*  ins;
        cs_err    err;

        cs_arch arch = MY_ARCH;
        err = cs_open(arch, MY_MODE, &h);
        if (err) {
            fprintf(stderr, "cs_open: %s\n", cs_strerror(err));
            panic(cs_strerror(err));
        }

        err = cs_option(h, CS_OPT_DETAIL, CS_OPT_ON);
        if (err) {
            fprintf(stderr, "cs_option: %s\n", cs_strerror(err));
            panic(cs_strerror(err));
        }

        ins = cs_malloc(h);
        if (ins == nil)
            panic("cs_malloc failed");

        const byte* code = (const byte*)cfunc;
        size_t      size = 10*1024; // something sane and limited
        uint64_t    addr = (uint64_t)cfunc;
        uint64_t    maxjump = addr;
        while (cs_disasm_iter(h, &code, &size, &addr, ins)) {
            if (debug)
                fprintf(stderr, "0x%" PRIx64 ":\t%s\t\t%s\n", ins->address, ins->mnemonic, ins->op_str);

            if (cs_insn_group(h, ins, CS_GRP_RET)) {
                if (ins->address >= maxjump)
                    break;
                continue;
            }

            uint64_t imm1;
            bool     imm1ok;
            tie(imm1, imm1ok) = _insn_getimm1(arch, ins);

            bool call = cs_insn_group(h, ins, CS_GRP_CALL);
            bool jump = cs_insn_group(h, ins, CS_GRP_JUMP) && !call;  // e.g. BL on arm64 is both jump and call

            if (jump && imm1ok) {
                maxjump = max(maxjump, imm1);
                continue;
            }

            if (call && imm1ok) {
                void* callee = (void*)imm1;
                if (debug)
                    fprintf(stderr, "  *** DIRECT CALL -> %p\n", callee);
                if (!std::count(vcallee.begin(), vcallee.end(), callee))
                    vcallee.push_back(callee);
            }
        }

        if (debug)
            fprintf(stderr, "\n");

        cs_free(ins, 1);
        cs_close(&h);
        return vcallee;
    }

    // _insn_getimm1 checks whether instruction comes with the sole immediate operand and returns it.
    static std::tuple<uint64_t, bool> _insn_getimm1(cs_arch arch, cs_insn* ins) {
        using namespace golang;
        using std::make_tuple;

        switch (arch) {
        case CS_ARCH_X86: {
            cs_x86* x86 = &(ins->detail->x86);
            if (x86->op_count == 1) {
                cs_x86_op* op = &(x86->operands[0]);
                if (op->type == X86_OP_IMM)
                    return make_tuple(op->imm, true);
            }
            break;
        }

        case CS_ARCH_ARM64: {
            cs_arm64* arm64 = &(ins->detail->arm64);
            if (arm64->op_count == 1) {
                cs_arm64_op* op = &(arm64->operands[0]);
                if (op->type == ARM64_OP_IMM)
                    return make_tuple(op->imm, true);
            }
            break;
        }

        default:
            panic("TODO");
        }

        return make_tuple(0, false);
    }


    int cfunc_is_callee_cleanup(void *cfunc) {
        // only i386 might have callee-cleanup
        // https://en.wikipedia.org/wiki/X86_calling_conventions#List_of_x86_calling_conventions
        if (!(MY_ARCH == CS_ARCH_X86 && MY_MODE == CS_MODE_32))
            return 0;

        const bool debug = false;

        int stkclean_by_callee = 0;
        using namespace golang;

        csh       h;
        cs_insn*  ins;
        cs_err    err;

        err = cs_open(MY_ARCH, MY_MODE, &h);
        if (err) {
            fprintf(stderr, "cs_open: %s\n", cs_strerror(err));
            panic(cs_strerror(err));
        }

        err = cs_option(h, CS_OPT_DETAIL, CS_OPT_ON);
        if (err) {
            fprintf(stderr, "cs_option: %s\n", cs_strerror(err));
            panic(cs_strerror(err));
        }

        ins = cs_malloc(h);
        if (ins == nil)
            panic("cs_malloc failed");

        const byte* code = (const byte*)cfunc;
        size_t      size = 10*1024; // something sane and limited
        uint64_t    addr = (uint64_t)cfunc;
        while (cs_disasm_iter(h, &code, &size, &addr, ins)) {
            if (debug)
                fprintf(stderr, "0x%" PRIx64 ":\t%s\t\t%s\n", ins->address, ins->mnemonic, ins->op_str);

            if (!cs_insn_group(h, ins, CS_GRP_RET))
                continue;

            assert(ins->id == X86_INS_RET);
            cs_x86* x86 =  &(ins->detail->x86);
            if (x86->op_count > 0) {
                cs_x86_op* op = &(x86->operands[0]);
                if (op->type == X86_OP_IMM)
                    stkclean_by_callee = op->imm;
            }

            break;
        }

        if (debug)
            fprintf(stderr, "  *** CLEANUP BY: %s  (%d)\n", (stkclean_by_callee ? "callee" : "caller"), stkclean_by_callee);

        cs_free(ins, 1);
        cs_close(&h);
        return stkclean_by_callee;
    }

    std::string cfunc_disasm(void *cfunc) {
        using namespace golang;
        string disasm;

        csh       h;
        cs_insn*  ins;
        cs_err    err;

        err = cs_open(MY_ARCH, MY_MODE, &h);
        if (err) {
            fprintf(stderr, "cs_open: %s\n", cs_strerror(err));
            panic(cs_strerror(err));
        }

        err = cs_option(h, CS_OPT_DETAIL, CS_OPT_ON);
        if (err) {
            fprintf(stderr, "cs_option: %s\n", cs_strerror(err));
            panic(cs_strerror(err));
        }

        ins = cs_malloc(h);
        if (ins == nil)
            panic("cs_malloc failed");

        const byte* code = (const byte*)cfunc;
        size_t      size = 10*1024; // something sane and limited
        uint64_t    addr = (uint64_t)cfunc;
        while (cs_disasm_iter(h, &code, &size, &addr, ins)) {
            disasm += fmt::sprintf("0x%" PRIx64 ":\t%s\t\t%s\n", ins->address, ins->mnemonic, ins->op_str);

            // FIXME also handle forward jump like cfunc_direct_callees does
            //       should be done automatically after DisasmIter dedup
            if (cs_insn_group(h, ins, CS_GRP_RET))
                break;
        }

        cs_free(ins, 1);
        cs_close(&h);

        return disasm;
    }
    """
    vector[void*] cfunc_direct_callees(void* cfunc)
    int cfunc_is_callee_cleanup(void* cfunc)
    string cfunc_disasm(void* cfunc)


# _test_inside_counted depends on inside_counted and funchook, which we don't want to expose.
# -> include the test from here. Do the same for other low-level tests.
include '_golang_str_pickle_test.pyx'


# ---- misc ----

cdef PyMethodDef* tp_methods_lookup(PyMethodDef* methv, str name) except NULL:
    m = &methv[0]
    while m.ml_name != NULL:
        if str(m.ml_name) == name:
            return m
        m += 1
    raise KeyError("method %s not found" % name)

cdef PyMemberDef* tp_members_lookup(PyMemberDef* membv, str name) except NULL:
    m = &membv[0]
    while m.name != NULL:
        if str(m.name) == name:
            return m
        m += 1
    raise KeyError("member %s not found" % name)
