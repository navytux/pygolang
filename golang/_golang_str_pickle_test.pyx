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

# test for inside_counted
def _test_inside_counted(): # -> outok
    outok = ''

    outok += '\n\n\nBEFORE PATCH\n'
    print('\n\n\nBEFORE PATCH')
    tfunc(3)

    t0 = ''
    for i in range(3,0-1,-1):
        t0 += '> tfunc(%d)\tinside_counter: 0\n' % i
    for i in range(0,3+1,+1):
        t0 += '< tfunc(%d)\tinside_counter: 0\n' % i
    outok += t0

    outok += '\n\n\nPATCHED\n'
    print('\n\n\nPATCHED')
    _patch = xfunchook_create()
    global inside_counted_func
    inside_counted_func = <void*>&tfunc
    xfunchook_prepare(_patch, &inside_counted_func, <void*>inside_counted)
    xfunchook_install(_patch, 0)

    tfunc(12)

    stk_size = 8  # = STK_SIZE from _golang_str_pickle.S
    for i in range(12,0-1,-1):
        outok += '> tfunc(%d)\tinside_counter: %d\n' % (i, min(12-i+1, stk_size))
    for i in range(0,12+1,+1):
        outok += '< tfunc(%d)\tinside_counter: %d\n' % (i, min(12-i+1, stk_size))

    outok += '\n\n\nUNPATCHED\n'
    print('\n\n\nUNPATCHED')
    xfunchook_uninstall(_patch, 0)
    tfunc(3)
    outok += t0

    return outok

cdef void tfunc(int x):
    print('> tfunc(%d)\tinside_counter: %d' % (x, inside_counter))
    if x > 0:
        tfunc(x-1)
    print('< tfunc(%d)\tinside_counter: %d' % (x, inside_counter))


def _test_cfunc_is_callee_cleanup():
    for t in _cfunc_is_callee_cleanup_testv:
        stkclean = cfunc_is_callee_cleanup(t.cfunc)
        assert stkclean == t.stkclean_by_callee_ok, (t.cfunc_name, stkclean, t.stkclean_by_callee_ok)

cdef extern from * nogil:
    r"""
    struct _Test_cfunc_is_callee_clenup {
        const char* cfunc_name;
        void*       cfunc;
        int         stkclean_by_callee_ok;
    };

    #define CASE(func, stkclean_ok) \
        _Test_cfunc_is_callee_clenup{#func, (void*)func, stkclean_ok}

    #if defined(LIBGOLANG_ARCH_386)
    int CALLCONV(cdecl)
    tfunc_cdecl1(int x)                     { return x; }
    int CALLCONV(cdecl)
    tfunc_cdecl2(int x, int y)              { return x; }
    int CALLCONV(cdecl)
    tfunc_cdecl3(int x, int y, int z)       { return x; }

    int CALLCONV(stdcall)
    tfunc_stdcall1(int x)                   { return x; }
    int CALLCONV(stdcall)
    tfunc_stdcall2(int x, int y)            { return x; }
    int CALLCONV(stdcall)
    tfunc_stdcall3(int x, int y, int z)     { return x; }

    int CALLCONV(fastcall)
    tfunc_fastcall1(int x)                  { return x; }
    int CALLCONV(fastcall)
    tfunc_fastcall2(int x, int y)           { return x; }
    int CALLCONV(fastcall)
    tfunc_fastcall3(int x, int y, int z)    { return x; }

    #ifndef LIBGOLANG_CC_msc    // see note about C3865 in FOR_EACH_CALLCONV
    int CALLCONV(thiscall)
    tfunc_thiscall1(int x)                  { return x; }
    int CALLCONV(thiscall)
    tfunc_thiscall2(int x, int y)           { return x; }
    int CALLCONV(thiscall)
    tfunc_thiscall3(int x, int y, int z)    { return x; }
    #endif

    #ifndef LIBGOLANG_CC_msc    // no regparm on MSCV
    int CALLCONV(regparm(1))
    tfunc_regparm1_1(int x)                 { return x; }
    int CALLCONV(regparm(1))
    tfunc_regparm1_2(int x, int y)          { return x; }
    int CALLCONV(regparm(1))
    tfunc_regparm1_3(int x, int y, int z)   { return x; }

    int CALLCONV(regparm(2))
    tfunc_regparm2_1(int x)                 { return x; }
    int CALLCONV(regparm(2))
    tfunc_regparm2_2(int x, int y)          { return x; }
    int CALLCONV(regparm(2))
    tfunc_regparm2_3(int x, int y, int z)   { return x; }

    int CALLCONV(regparm(3))
    tfunc_regparm3_1(int x)                 { return x; }
    int CALLCONV(regparm(3))
    tfunc_regparm3_2(int x, int y)          { return x; }
    int CALLCONV(regparm(3))
    tfunc_regparm3_3(int x, int y, int z)   { return x; }
    #endif

    static std::vector<_Test_cfunc_is_callee_clenup> _cfunc_is_callee_cleanup_testv = {
        CASE(tfunc_cdecl1     , 0 * 4),
        CASE(tfunc_cdecl2     , 0 * 4),
        CASE(tfunc_cdecl3     , 0 * 4),
        CASE(tfunc_stdcall1   , 1 * 4),
        CASE(tfunc_stdcall2   , 2 * 4),
        CASE(tfunc_stdcall3   , 3 * 4),
        CASE(tfunc_fastcall1  , 0 * 4),
        CASE(tfunc_fastcall2  , 0 * 4),
        CASE(tfunc_fastcall3  , 1 * 4),
    #ifndef LIBGOLANG_CC_msc
        CASE(tfunc_thiscall1  , 0 * 4),
        CASE(tfunc_thiscall2  , 1 * 4),
        CASE(tfunc_thiscall3  , 2 * 4),
    #endif
    #ifndef LIBGOLANG_CC_msc
        CASE(tfunc_regparm1_1 , 0 * 4),
        CASE(tfunc_regparm1_2 , 0 * 4),
        CASE(tfunc_regparm1_3 , 0 * 4),
        CASE(tfunc_regparm2_1 , 0 * 4),
        CASE(tfunc_regparm2_2 , 0 * 4),
        CASE(tfunc_regparm2_3 , 0 * 4),
        CASE(tfunc_regparm3_1 , 0 * 4),
        CASE(tfunc_regparm3_2 , 0 * 4),
        CASE(tfunc_regparm3_3 , 0 * 4),
    #endif
    };

    #else
    // only i386 has many calling conventions
    int tfunc_default(int x, int y, int z)      { return x; }

    static std::vector<_Test_cfunc_is_callee_clenup> _cfunc_is_callee_cleanup_testv = {
        CASE(tfunc_default, 0),
    };
    #endif

    #undef CASE
    """
    struct _Test_cfunc_is_callee_clenup:
        const char* cfunc_name
        void*       cfunc
        int         stkclean_by_callee_ok

    vector[_Test_cfunc_is_callee_clenup] _cfunc_is_callee_cleanup_testv
