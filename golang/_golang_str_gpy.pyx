# -*- coding: utf-8 -*-
# Copyright (C) 2023-2026  Nexedi SA and Contributors.
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
"""_golang_str_gpy.pyx complements _golang_str.pyx and keeps everything
related to patching str/unicode to be replaced by bstr/ustr under gpython.

It is included from _golang_str.pyx .

See also _golang_str_pickle_gpy.pyx .
"""

from cpython cimport Py_TPFLAGS_HAVE_GC, Py_TPFLAGS_READY, PyType_Ready
from cpython cimport Py_TPFLAGS_VALID_VERSION_TAG, Py_TPFLAGS_HAVE_VERSION_TAG
from cpython cimport PyBytes_Format, PyUnicode_Format, PyObject_Str
from cpython cimport PyObject_GetAttr, PyObject_SetAttr, PyObject_HasAttr
from cpython cimport PyBytes_Check

cdef extern from "Python.h":
    ctypedef struct PyVarObject:
        Py_ssize_t ob_size

import weakref as pyweakref


# XXX place, comments
# str % ... : ceval on py2 and py3 < 3.11 invokes PyString_Format / PyUnicode_Format
#   directly upon seeing BINARY_MODULO. This leads to bstr.__mod__ not being called.
# XXX -> patch PyString_Format / PyUnicode_Format to invoke our .__mod__ ...
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
# py3.11: specializes instructions. e.g. ustr(obj) will specialize (after
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


# XXX place, comments, test
# on py3 PyObject_GetAttr & co insist on name to be unicode
# XXX _PyObject_GenericGetAttrWithDict
# XXX _PyObject_GenericSetAttrWithDict
# XXX type_getattro
# XXX type.__new__
#     In [11]: type.__new__(type, bstr('aaa'), (int,), {})
#     TypeError: type.__new__() argument 1 must be str, not golang.bstr
IF PY3:
    # XXX dup wrt _golang_str_test.pyx
    cdef extern from "Python.h":
        """
        // before py3.13 PyObject_GetOptionalAttr was named as _PyObject_LookupAttr
        #if PY_VERSION_HEX < 0x030D0000 // 3.13
        # define PyObject_GetOptionalAttr _PyObject_LookupAttr
        #endif
        """
        int PyObject_GetOptionalAttr(object obj, object attr, PyObject** pres) except -1

    ctypedef object obj_getattr_func(object, object)
    ctypedef int    obj_setattr_func(object, object, object) except -1
    #               delattr is implemented via setattr(v=NULL)
    ctypedef bint   obj_hasattr_func(object, object) # no except
    ctypedef int    obj_getxattr_func(object, object, PyObject**) except -1

    cdef obj_getattr_func*  _pobject_GetAttr    = PyObject_GetAttr
    cdef obj_setattr_func*  _pobject_SetAttr    = PyObject_SetAttr
    cdef obj_hasattr_func*  _pobject_HasAttr    = PyObject_HasAttr
    cdef obj_getxattr_func* _pobject_GetXAttr   = PyObject_GetOptionalAttr

    # isbstr returns whether obj is bstr instance or not.
    # it avoids going to isinstance unless really needed because isinstance,
    # internally, uses PyObject_GetOptionalAttr and we need to patch that function
    # with using isbstr in the hook.
    cdef bint isbstr(obj) except -1:
        if not PyBytes_Check(obj):
            return False
        if Py_TYPE(obj) == <PyTypeObject*>pybstr:
            return True
        # it might be also a pybstr subclass
        return isinstance(obj, pybstr)

    cdef object _object_xGetAttr(object obj, object name):
        if isbstr(name):
            name = pyustr(name)
        return _pobject_GetAttr(obj, name)

    cdef int    _object_xSetAttr(object obj, object name, object v) except -1:  # XXX v=NULL on del
        if isbstr(name):
            name = pyustr(name)
        return _pobject_SetAttr(obj, name, v)

    cdef bint   _object_xHasAttr(object obj, object name): # no except
        if isbstr(name):
            name = pyustr(name)
        return _pobject_HasAttr(obj, name)


    cdef int    _object_xGetXAttr(object obj, object name, PyObject** pres) except -1:
        if isbstr(name):
            name = pyustr(name)
        return _pobject_GetXAttr(obj, name, pres)


cdef _patch_capi_object_attr_bstr():
    IF PY3:
        cpatch(<void**>&_pobject_GetAttr,       <void*>_object_xGetAttr)
        cpatch(<void**>&_pobject_SetAttr,       <void*>_object_xSetAttr)
        cpatch(<void**>&_pobject_HasAttr,       <void*>_object_xHasAttr)
        cpatch(<void**>&_pobject_GetXAttr,      <void*>_object_xGetXAttr)

        # py3 < 3.11 also verifies name to be unicode
        # XXX move out of _patch_capi* ?
        import builtins
        cdef object builtins_getattr = builtins.getattr
        cdef object builtins_setattr = builtins.setattr
        cdef object builtins_delattr = builtins.delattr
        cdef object builtins_hasattr = builtins.hasattr

        def xgetattr(obj, name, *argv):
            if isbstr(name):
                name = pyustr(name)
            return builtins_getattr(obj, name, *argv)
        def xsetattr(obj, name, value):
            if isbstr(name):
                name = pyustr(name)
            return builtins_setattr(obj, name, value)
        def xdelattr(obj, name):
            if isbstr(name):
                name = pyustr(name)
            return builtins_delattr(obj, name)
        def xhasattr(obj, name):
            if isbstr(name):
                name = pyustr(name)
            return builtins_hasattr(obj, name)

        builtins.getattr = xgetattr
        builtins.setattr = xsetattr
        builtins.delattr = xdelattr
        builtins.hasattr = xhasattr


# ---- funchook wrappers -----

cdef extern from "funchook.h" nogil:
    ctypedef struct funchook_t
    funchook_t* funchook_create()
    int funchook_prepare(funchook_t* h, void** target_func, void* hook_func)
    int funchook_install(funchook_t* h, int flags)
    int funchook_uninstall(funchook_t* h, int flags)
    int funchook_destroy(funchook_t*)
    const char* funchook_error_message(const funchook_t*)
    int funchook_set_debug_file(const char* name)

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
# XXX and make sure golang._golang._pybstr cannot be imported as well  (ex pickle)  -> del _pybstr
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

    # patch unicode to be pyustr. This patches
    # - unicode (py2)
    # - str     (py3)
    uidx = pytype_staticbuiltin_to_static(<PyTypeObject*>unicode)
    _pytype_clone(<PyTypeObject*>unicode, &_unicode_orig, "unicode(pystd)")
    Py_INCREF(unicode)  # XXX needed?
    zunicode = <object>&_unicode_orig

    _pytype_replace_by_child(
            <PyTypeObject*>unicode, &_unicode_orig,
            <PyTypeObject*>pyustr, "ustr(origin)",
            upreserve_slots)
    pyustr = unicode    # retarget pyustr -> unicode to where it was copied
    # XXX vvv needed so that patched unicode could be saved by py2:cPickle at all
    # XXX vvv should be done by pytype_replace... ?  just us original unicode.tp_name ? -> yes
    (<PyTypeObject*>pyustr).tp_name = ("unicode" if PY_MAJOR_VERSION < 3  else "str")
    pytype_static_to_staticbuiltin(<PyTypeObject*>unicode, uidx)

    # py2: patch str to be pybstr
    if PY_MAJOR_VERSION < 3:
        bidx = pytype_staticbuiltin_to_static(<PyTypeObject*>bytes)
        _pytype_clone(<PyTypeObject*>bytes, &_bytes_orig, "bytes(pystd)")
        Py_INCREF(bytes)    # XXX needed?
        zbytes = <object>&_bytes_orig

        _pytype_replace_by_child(
                <PyTypeObject*>bytes, &_bytes_orig,
                <PyTypeObject*>_pybstr, "bstr(origin)",
                bpreserve_slots)
        pybstr = bytes  # retarget pybstr -> bytes to where it was copied
        (<PyTypeObject*>pybstr).tp_name = ("str" if PY_MAJOR_VERSION < 3  else "bytes")
        pytype_static_to_staticbuiltin(<PyTypeObject*>bytes, bidx)

    # need to remove unsupported slots in cloned bstr/ustr again since PyType_Ready might have recreated them
    _bstrustr_remove_unsupported_slots()


    # also patch UserString to have methods that bstr/ustr have
    # else on py3 IPython's guarded_eval.py fails in `_list_methods(collections.UserString, dir(str))`
    from six.moves import UserString
    def userstr__bytes__(s):    return bytes(s.data)
    def userstr__unicode__(s):  return unicode(s.data)
    def userstr_decode(s, encoding=None, errors=None):
                                return pyb(s.data).decode(encoding, errors)
    assert not hasattr(UserString, '__bytes__')         # XXX test
    assert not hasattr(UserString, '__unicode__')
    UserString.__bytes__   = userstr__bytes__
    UserString.__unicode__ = userstr__unicode__
    if PY_MAJOR_VERSION >= 3:
        assert not hasattr(UserString, 'decode')
        UserString.decode  = userstr_decode

    # ideally assert that dir(UserString) == dir(str), but UserString has more methods, e.g. __float__
    # check only that dir(str) ⊆ dir(UserString)
    #
    # on py2 str has many things that UserString does not have: e.g. __ne__, __le__, ...
    if PY_MAJOR_VERSION >= 3:
        dir_UserString = set(dir(UserString))
        dir_str        = set(dir(str))
        assert dir_str.issubset(dir_UserString),  dir_str.difference(dir_UserString)


    # XXX also patch CAPI functions ... XXX explain
    #funchook_set_debug_file("/dev/stderr")  # XXX add runtime opt to activate this
    _patch_capi_hook = xfunchook_create()

    _patch_capi_str_format()
    _patch_capi_object_str()
    _patch_capi_object_attr_bstr()  # XXX activate under plain py as well
    _patch_capi_unicode_decode_as_bstr()
    _patch_str_pickle()
    # ...

    xfunchook_install(_patch_capi_hook, 0)


# _pytype_clone clones PyTypeObject src into dst.
#
# src must be not heap-allocated type.
# dst must be statically allocated and not previously initialized.
#
# dst will have reference-count = 1 meaning new reference to the clone is returned.
cdef _pytype_clone(PyTypeObject *src, PyTypeObject *dst, const char* new_name):
    assert (src.tp_flags & Py_TPFLAGS_READY) != 0
    assert (src.tp_flags & Py_TPFLAGS_HEAPTYPE) == 0    # src is not allocated on heap
                                                        # and so GC for it is disabled
    # copy the struct   XXX + ._ob_next / ._ob_prev (set to NULL) (Py_TRACE_REFS < 3.13; 3.13 switched to oob hashtable)
    dst[0] = src[0]
    (<PyObject*>dst).ob_refcnt = 1

    if new_name != NULL:
        dst.tp_name = new_name

    # now reinitialize things like .tp_dict etc, where PyType_Ready built slots that point to src.
    # we want all those slots to be rebuilt and point to dst instead.
    # XXX test
    _dst = <_XPyTypeObject*>dst
    dst .tp_flags &= ~Py_TPFLAGS_READY
    dst .tp_dict     = NULL     # XXX -> PyType_SetDict
    _dst.tp_bases    = NULL
    _dst.tp_mro      = NULL
    _dst.tp_cache    = NULL
    _dst.tp_weaklist = NULL

    # dst.__subclasses__ will be empty because existing children inherit from src, not from dst.
    # XXX but ustr, after copy to unicode, will inherit from unicode(pystd)  -- recheck
    # XXX test
    _dst.tp_subclasses = NULL

    # XXX -> common reinherit fixup
    # XXX not correct if there are several bases -> need to check whole mro
    if _dst.tp_init == (<_XPyTypeObject*>(dst.tp_base)).tp_init:
        _dst.tp_init = NULL

    # XXX .tp_version_tag = 0  + clear flag ?
    PyType_Ready(<object>dst)
    assert (dst.tp_flags & Py_TPFLAGS_READY) != 0
    assert (dst.tp_flags & Py_TPFLAGS_HEAPTYPE) == 0

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
# typ and egg must be static non heap-allocated types.
#
# typ_clone must be initialized via _pytype_clone(typ, typ_clone).
# egg' is egg clone put inplace of typ.
#
# XXX preserve_slots - describe
#
# XXX consider combining _pytype_clone + _pytype_replace_by_child -> _pytype_pivot_chile
#     and avoid typ_clone at all
cdef _pytype_replace_by_child(PyTypeObject *typ, PyTypeObject *typ_clone,
                              PyTypeObject *egg, const char* egg_old_name,
                              preserve_slots):
    otyp = <PyObject*>typ           ; oegg = <PyObject*>egg
    vtyp = <PyVarObject*>typ        ; vegg = <PyVarObject*>egg
    _typ = <_XPyTypeObject*>typ     ; _egg = <_XPyTypeObject*>egg

    assert egg.tp_base == typ
    assert _egg.tp_subclasses == NULL

    assert <object>_egg.tp_bases == (<object>egg.tp_base,)
    assert <object>_typ.tp_bases == (<object>typ.tp_base,)

    assert (typ.tp_flags & Py_TPFLAGS_READY)  != 0
    assert (egg.tp_flags & Py_TPFLAGS_READY)  != 0

    assert (typ.tp_flags & Py_TPFLAGS_HEAPTYPE) == 0
    assert (egg.tp_flags & Py_TPFLAGS_HEAPTYPE) == 0

    # (generally not required)
    assert (typ.tp_flags & Py_TPFLAGS_HAVE_GC) == 0
    assert (egg.tp_flags & Py_TPFLAGS_HAVE_GC) == 0

    assert vtyp.ob_size               ==  vegg.ob_size
    assert typ .tp_basicsize          ==  egg .tp_basicsize
    assert typ .tp_itemsize           ==  egg .tp_itemsize
    IF PY3:
        assert _typ.tp_vectorcall_offset  ==  _egg.tp_vectorcall_offset
    assert _typ.tp_weaklistoffset     ==  _egg.tp_weaklistoffset
    assert typ .tp_dictoffset         ==  egg .tp_dictoffset

    # XXX py >= 3.12
    # assert egg.tp_flags & _Py_TPFLAGS_STATIC_BUILTIN == 0
    # assert typ.tp_flags & _Py_TPFLAGS_STATIC_BUILTIN != 0


    # since egg will change .tp_base it will also need to reinitialize
    # .tp_bases, .tp_mro and friends. Retrieve egg slots to preserve before we
    # clear egg.__dict__ . This covers e.g. @staticmethod and @property.
    keep_slots = {}  # name -> slot
    for name in preserve_slots:
        keep_slots[name] = _get_slot(egg, name)


    # before we start to adjust typ, prepare all its children to reinherit after typ is patched
    #
    # for example we need to set .tp_init=NULL if __init__ was not overwritten
    # and inherited from base type so that it is reinherited again from patched typ.tp_init .
    # we also need to reset e.g. .tp_mro because egg will be injected into
    # inheritance chain.
    egg_tp_dealloc = egg.tp_dealloc
    typ_topo_subclasses = _topo_subclasses(<object>typ)
    for X in reversed(typ_topo_subclasses): # depth-first
        _reinherit_prepare(X)


    # egg: clear what PyType_Ready will recompute besides what was cleared by reinherit_prepare
    Py_CLEAR(egg .tp_dict)
    Py_CLEAR(_egg.tp_bases)

    # typ <- egg  preserving original typ's refcnt, weak references and subclasses\egg.
    # typ will be now playing the role of egg
    typ_refcnt     = otyp.ob_refcnt
    # XXX py3.12 "For the static builtin types this is always NULL, even if weakrefs are added ..."
    typ_weaklist   = _typ.tp_weaklist
    # XXX py3.12 "May be an invalid pointer" (for static builtin types it became `size_t index`
    typ_subclasses = _typ.tp_subclasses
    xtyp_subclasses = <object>typ_subclasses

    # remove egg from typ's subclasses  (.tp_subclasses is dict on py3 and list on py2)
    # https://github.com/python/cpython/commit/84745ab464f9
    if PY_MAJOR_VERSION >= 3:
        assert type(xtyp_subclasses) is dict    # {} id -> subclass
        del xtyp_subclasses[id(<object>egg)]
    else:
        assert type(xtyp_subclasses) is list    # [] of weakref(subclass)
        for i, _ in reversed(list(enumerate(xtyp_subclasses))):
            assert type(_) is pyweakref.ref
            if _() is <object>egg:
                del xtyp_subclasses[i]

    typ[0] = egg[0]
    otyp.ob_refcnt     = typ_refcnt
    _typ.tp_weaklist   = typ_weaklist
    _typ.tp_subclasses = typ_subclasses

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


    # when e.g. unicode will be PyType_Ready'ed it creates and destroys
    # unicode objects for slotnames before inheriting .tp_dealloc from parent.
    # preset .tp_dealloc manually to avoid the crash.
    assert typ.tp_dealloc == NULL
    typ.tp_dealloc = egg_tp_dealloc

    _reinherit_reready(<object>typ)

    # XXX remove typ from base.tp_subclasses
    #     else e.g. ustr(origin) is reported to be subclass of ustr by help()
    #     (pyustr.__subclasses__()  give it)

    # rebuild .tp_mro of all other typ's children
    # initially X.__mro__ = (X, typ, base) and without rebuilding it would
    # remain (X, egg', base) instead of correct (X, egg' typ_clone, base)
    # XXX py3 does this automatically?  XXX -> no, it can invalidate .__mro__, but not .tp_mro
    # XXX yes -> we clear .tp_mro ^^^ and it gets recomputed, right?

    for X in typ_topo_subclasses:   # top-down
        _reinherit_reready(X)

    XPyType_Modified(typ)

    # py fini for static types asserts that many .tp_* are immortal
    # XXX if ver
    py_setimmortal(_typ.tp_bases)
    py_setimmortal(_typ.tp_mro)

    # XXX also preserve ._ob_next + ._ob_prev  (present in Py_TRACE_REFS builds for < 3.13)

    # restore slots we were asked to preserve as is
    # since those slots are e.g. @staticmethods they go to both egg' and egg.
    for name, slot in keep_slots.items():
        _patch_slot(typ, name, slot, asis=True)
#       _patch_slot(egg, name, slot, asis=True)     NOTE will go away after !typ_clone



# pytype_staticbuiltin_to_static converts static builtin type to just static type.
# pytype_static_to_staticbuiltin does the opposite.
#
# py_setimmortal switches an object to be immportal, if supported.
cdef extern from *:
    r"""
    #if PY_VERSION_HEX >= 0x030C0000    // 3.12
    # ifndef Py_BUILD_CORE
    #  define Py_BUILD_CORE 1
    # endif
    # if PY_VERSION_HEX < 0x030D0000    // 3.13
        using namespace std; // to avoid compile errors in py atomics on 3.12
                             // FIXME stil fails to build on 3.12 (3.13 + 3.14 are ok)
    # endif
    # include "internal/pycore_object.h"
    # include "internal/pycore_interp.h"

    # if PY_VERSION_HEX < 0x030D0000    // 3.13
    #  define _Py_MAX_MANAGED_STATIC_BUILTIN_TYPES  _Py_MAX_STATIC_BUILTIN_TYPES
    #  define managed_static_type_state             static_builtin_state
    # endif

    using golang::panic;

    // _XPyStaticType_Index returns index of static type.
    size_t _XPyStaticType_Index(PyTypeObject* typ) {
        // cpython stores 1-based index in typ.tp_subclasses
        if (typ->tp_subclasses == NULL)
            panic("type index is not set");
        size_t tindex = (size_t)typ->tp_subclasses - 1;
        if (!(0 <= tindex && tindex < _Py_MAX_MANAGED_STATIC_BUILTIN_TYPES))
            panic("type index out of range");
        return tindex;
    }

    // _XPyStaticType_GetState return interpreter state corresponding to static type.
    managed_static_type_state* _XPyStaticType_GetState(PyTypeObject* typ) {
        if (!(typ->tp_flags & _Py_TPFLAGS_STATIC_BUILTIN))
            panic("type is not static builtin");
        size_t tindex = _XPyStaticType_Index(typ);

        PyInterpreterState*        interp = PyInterpreterState_Get();
        managed_static_type_state* tstate = &(interp->types.builtins
    #   if PY_VERSION_HEX >= 0x030D0000 // 3.13
                                                        .initialized
    #   endif
                                                                    [tindex]);

        if (tstate->type != typ)
            panic("tstate->type != type");

        return tstate;
    }

    size_t pytype_staticbuiltin_to_static(PyTypeObject* typ) {
        if (!(typ->tp_flags & _Py_TPFLAGS_STATIC_BUILTIN))
            panic("type is not static builtin");
        // XXX also immortal?

        if (_py_n_interpreters() != 1)
            panic("py interpreter is not singleton");
        managed_static_type_state* tstate = _XPyStaticType_GetState(typ);
        size_t                     tindex = _XPyStaticType_Index(typ);

        if (typ->tp_dict)       panic("type.tp_dict not NULL");
        if (typ->tp_weaklist)   panic("type.tp_weaklist not NULL");
        //  typ->tp_subclasses is non-NULL and already checked by _XPyStaticType_Index

        tstate->type = NULL;
        typ->tp_dict       = tstate->tp_dict;        tstate->tp_dict       = NULL;
        typ->tp_weaklist   = tstate->tp_weaklist;    tstate->tp_weaklist   = NULL;
        typ->tp_subclasses = tstate->tp_subclasses;  tstate->tp_subclasses = NULL;

        typ->tp_flags &= ~_Py_TPFLAGS_STATIC_BUILTIN;
        return tindex;
    }

    void pytype_static_to_staticbuiltin(PyTypeObject* typ, size_t tindex) {
        if (typ->tp_flags & _Py_TPFLAGS_STATIC_BUILTIN)
            panic("type is already static builtin");
        if (!(0 <= tindex && tindex < _Py_MAX_MANAGED_STATIC_BUILTIN_TYPES))
            panic("type index out of range");

        if (_py_n_interpreters() != 1)
            panic("py interpreter is not singleton");

        PyInterpreterState*        interp = PyInterpreterState_Get();
        managed_static_type_state* tstate = &(interp->types.builtins
    #   if PY_VERSION_HEX >= 0x030D0000 // 3.13
                                                        .initialized
    #   endif
                                                                    [tindex]);

        if (tstate->type)           panic("tstate slot already busy");
        if (tstate->tp_dict)        panic("tstate.tp_dict not NULL");
        if (tstate->tp_weaklist)    panic("tstate.tp_weaklist not NULL");
        if (tstate->tp_subclasses)  panic("tstate.tp_subclasses not NULL");
        tstate->type = typ;
        tstate->tp_dict       = typ->tp_dict;        typ->tp_dict = NULL;
        tstate->tp_weaklist   = typ->tp_weaklist;    typ->tp_weaklist = NULL;

        tstate->tp_subclasses = (PyObject*)(typ->tp_subclasses);
        typ   ->tp_subclasses = (PyObject*)(tindex+1);

        typ->tp_flags |= _Py_TPFLAGS_STATIC_BUILTIN;
    }

    void py_setimmortal(PyObject* obj) {
    #   if PY_VERSION_HEX >= 0x030E0000 // 3.14 , present on 3.13 but unexported
        _Py_SetImmortal(obj);
    #   endif
    }

    #else   // < 3.12

    size_t pytype_staticbuiltin_to_static(PyTypeObject* typ)            { return 0; }
    void pytype_static_to_staticbuiltin(PyTypeObject* typ, size_t tdx)  {}
    void py_setimmortal(PyObject*)                                      {}

    #endif

    """
    size_t pytype_staticbuiltin_to_static(PyTypeObject*)
    void pytype_static_to_staticbuiltin(PyTypeObject*, size_t)
    void py_setimmortal(PyObject*)



# _reinherit_prepare prepares class X to reinherited from patched (sub)base.
cdef _reinherit_prepare(X):
    assert isinstance(X, type)
    x = <PyTypeObject*>X    ; _x = <_XPyTypeObject*>X

    if _debug:
        _debugf('prepare  %s(', x.tp_name)
        for i, B in enumerate(X.__bases__):
            assert isinstance(B, type)
            b = <PyTypeObject*>B
            if i > 0:
                _debugf(', ')
            _debugf('%s', b.tp_name)
        _debugf(')\n')

    X__bases__ = X.__bases__

    assert (x.tp_flags & Py_TPFLAGS_READY) != 0
    x.tp_flags &= ~Py_TPFLAGS_READY
    if type_have_version_tag(x):
        x.tp_flags &= ~Py_TPFLAGS_VALID_VERSION_TAG

    for B in X__bases__:
        assert isinstance(B, type)
        _reinherit_prepare1(<PyTypeObject*>B, x)

    Py_CLEAR(_x.tp_mro)     # to be rebuilt
    Py_CLEAR(_x.tp_cache)   # ----//----
    # XXX 3.12 +tp_watched
    # XXX 3.13+3.14 - recheck
    # .tp_bases: it is documented to be autobuilt, but when a type is created,
    #            or in our case recreated, via PyType_Ready .tp_bases is the
    #            only source of information for multi-inheritance bases. This
    #            way we leave it intact and do not clear.

# _reinherit_prepare1 resets x->tp_* fields, that were inherited from base, to NULL.
#
# Those fields will need to be reinitialized by PyType_Ready after base is patched.
# For details see
#
#   https://docs.python.org/3/c-api/typeobj.html -> inheritance + defaults
cdef extern from *:
    r"""
    void _reinherit_prepare1(PyTypeObject* base, PyTypeObject* x) {
    # define R(PROP) do {                                           \
        if (base->PROP != NULL && x->PROP == base->PROP) {          \
            _gpy_debugf("  .%s  <- %s\n", #PROP, base->tp_name);    \
            x->PROP = NULL;                                         \
            /* NOTE do not delete __new__ from dict:                \
               - when e.g. .tp_new is inherited -> __new__ is not created   \
               - but if custom __new__ was overwritten at py level - we have to preserve that */ \
            }                                                       \
        } while(0)

        // tp_basicsize:            asserted to be the same for unicode/ustr
        // tp_itemsize:             ----//----
        R(tp_dealloc);
        // tp_vectorcall_offset:    asserted to be same
        R(tp_getattr);
        R(tp_setattr);
        // XXX tp_as_async
        R(tp_repr);
        // XXX tp_as_number
        // XXX tp_as_sequence
        // XXX tp_as_mapping
        R(tp_hash);
        R(tp_call);
        R(tp_str);
        R(tp_getattro);
        R(tp_setattro);
        // XXX tp_as_buffer
        // XXX ? tp_flags
        // tp_traverse:   PyType_Ready insists on this to be initialized if Py_TPFLAGS_HAVE_GC is set
        // tp_clear:      ----//----
        R(tp_richcompare);
        // tp_weaklistoffset:       asserted to be same
        R(tp_iter);
        R(tp_iternext);
        R(tp_descr_get);
        R(tp_descr_set);
        // tp_dictoffset:           asserted to be same
        R(tp_init);
        // XXX ? tp_alloc
        R(tp_new);
        // XXX ? tp_free
        R(tp_is_gc);
    # if PY_MAJOR_VERSION >= 3
        R(tp_finalize);
    # endif

    # undef R
    }
    """
    void _reinherit_prepare1(PyTypeObject* base, PyTypeObject* x)


# _reinherit_reready readies class X after it was first _reinherit_prepared and its (sub)base patched.
cdef _reinherit_reready(X):
    assert isinstance(X, type)
    x = <PyTypeObject*>X
    _debugf('ready    %s\n', x.tp_name)

    assert (x.tp_flags & Py_TPFLAGS_READY) == 0
    if type_have_version_tag(x):
        assert (x.tp_flags & Py_TPFLAGS_VALID_VERSION_TAG) == 0

    PyType_Ready(X)

    assert (x.tp_flags & Py_TPFLAGS_READY) != 0
    if type_have_version_tag(x):
        if (x.tp_flags & Py_TPFLAGS_VALID_VERSION_TAG) == 0:
            hasattr(<object>x, 'whatever')  # _PyType_Lookup -> assign_version_tag
        assert (x.tp_flags & Py_TPFLAGS_VALID_VERSION_TAG) != 0


# type_have_version_tag tells whether `typ.tp_flags & Py_TPFLAGS_VALID_VERSION_TAG` could be checked.
cdef bint type_have_version_tag(PyTypeObject* typ):
    # Py_TPFLAGS_HAVE_VERSION_TAG is not set by default for extensions on py2 and is noop on py3.11+
    # https://github.com/python/cpython/commit/69ed1011aabd
    # https://github.com/python/cpython/commit/a4760cc32d9e
    return (PY_VERSION_HEX < 0x030B0000) and (typ.tp_flags & Py_TPFLAGS_HAVE_VERSION_TAG)


# _topo_subclasses returns all subclasses of typ in topological order from top->down.
cdef _topo_subclasses(typ):
    topo = []
    seen = set()
    def _(x):
        assert isinstance(x, type)
        if x in seen:
            return
        seen.add(x)
        for y in x.__subclasses__():
            _(y)
        topo.append(x)
    _(typ)
    assert topo[-1] is typ
    topo = topo[:-1]
    topo.reverse()
    return topo


# XXX place, text
cdef _get_slot(PyTypeObject* typ, str name):
    typdict = XPyType_GetDict(typ)
    return typdict[name]


cdef extern from "<stdio.h>":
    """
    static const int _gpy_debug = 0;
    static void _gpy_debugf(const char* format, ...) {
        if (!_gpy_debug)
            return;
        va_list ap;
        va_start(ap, format);
        vfprintf(stderr, format, ap);
        va_end(ap);
    }
    """
    bint _debug  "_gpy_debug"
    void _debugf "_gpy_debugf" (const char* format, ...)
