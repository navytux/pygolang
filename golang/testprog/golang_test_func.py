# -*- coding: utf-8 -*-
# Copyright (C) 2018-2025  Nexedi SA and Contributors.
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
"""This module helps to verify @func(cls) and just @func.

It complements golang_str_test.test_func which runs the code from here both as
a top-level module and inside a function activating changes marked by +funcfunc.
"""

from __future__ import print_function, absolute_import

from golang import func
from golang.golang_test import fmtargspec
import gc


if 1:       #def tmain():               +funcfunc
            #    cellvar = 123          +funcfunc
            #    del cellvar            +funcfunc
    if 1:   #    def _tmain():          +funcfunc
            #        nonlocal cellvar   +funcfunc +py3
        # test how @func(cls) works
        # this also implicitly tests just @func, since @func(cls) uses that.

        class MyClass(object):
            def __init__(self, v):
                self.v = v

        zzz = zzz_orig = 'z'    # `@func(MyClass) def zzz` must not override zzz
        @func(MyClass)
        def zzz(self, v, x=2, **kkkkwww):
            assert self.v == v
            return v + 1
        assert zzz is zzz_orig
        assert zzz == 'z'

        mstatic = mstatic_orig = 'mstatic'
        @func(MyClass)
        @staticmethod
        def mstatic(v):
            assert v == 5
            return v + 1
        assert mstatic is mstatic_orig
        assert mstatic == 'mstatic'

        mcls = mcls_orig = 'mcls'
        @func(MyClass)
        @classmethod
        def mcls(cls, v):
            assert cls is MyClass
            assert v == 7
            return v + 1
        assert mcls is mcls_orig
        assert mcls == 'mcls'

        # undefined var after `@func(cls) def var` should be not set
        # same for cellvar
        assert 'var'     not in locals()
        assert 'cellvar' not in locals()
        @func(MyClass)
        def var(self, v):
            assert v == 8
            return v + 1
        @func(MyClass)
        def cellvar(self, v):
            assert v == 9
            return v + 1
        gc.collect()    # pypy needs this to trigger _DelAttrAfterMeth GC
        assert 'var'     not in locals()
        assert 'cellvar' not in locals()


        vproperty = vproperty_orig = 'vproperty'
        @func(MyClass)
        @property
        def vproperty(self):
            """documentation for vproperty"""
            assert isinstance(self, MyClass)
            return 'v%s' % self.v
        assert vproperty is vproperty_orig
        assert vproperty == 'vproperty'

        @func(MyClass)
        @MyClass.vproperty.setter
        def _(self, v):
            assert isinstance(self, MyClass)
            self.v = v
        assert vproperty is vproperty_orig
        assert vproperty == 'vproperty'

        @func(MyClass)
        @MyClass.vproperty.deleter
        def _(self):
            assert isinstance(self, MyClass)
            self.v = 'deleted'
        assert vproperty is vproperty_orig
        assert vproperty == 'vproperty'


        obj = MyClass(4)
        assert obj.zzz(4)       == 4 + 1
        assert obj.mstatic(5)   == 5 + 1
        assert obj.mcls(7)      == 7 + 1
        assert obj.var(8)       == 8 + 1
        assert obj.cellvar(9)   == 9 + 1
        assert obj.v            == 4        # set by .zzz
        assert obj.vproperty    == 'v4'
        obj.vproperty = 5
        assert obj.v            == 5
        assert obj.vproperty    == 'v5'
        del obj.vproperty
        assert obj.v            == 'deleted'
        assert obj.vproperty    == 'vdeleted'
        assert MyClass.vproperty.__doc__ == "documentation for vproperty"""

        # this tests that @func (used by @func(cls)) preserves decorated function signature
        assert fmtargspec(MyClass.zzz) == '(self, v, x=2, **kkkkwww)'

        assert MyClass.zzz.__module__       == __name__
        assert MyClass.zzz.__name__         == 'zzz'

        assert MyClass.mstatic.__module__   == __name__
        assert MyClass.mstatic.__name__     == 'mstatic'

        assert MyClass.mcls.__module__      == __name__
        assert MyClass.mcls.__name__        == 'mcls'

        assert MyClass.var.__module__       == __name__
        assert MyClass.var.__name__         == 'var'

        assert MyClass.cellvar.__module__   == __name__
        assert MyClass.cellvar.__name__     == 'cellvar'

        assert MyClass.vproperty.fget.__module__    == __name__
        assert MyClass.vproperty.fset.__module__    == __name__
        assert MyClass.vproperty.fdel.__module__    == __name__
        assert MyClass.vproperty.fget.__name__      == 'vproperty'
        assert MyClass.vproperty.fset.__name__      == '_'
        assert MyClass.vproperty.fdel.__name__      == '_'

        # test that func·func = func  (double _func calls are done internally for
        # getter when handling @func(@MyClass.vproperty.setter)
        def f(): pass
        g = func(f)
        h = func(g)
        assert h is g

#    _tmain()                           +funcfunc
#tmain()                                +funcfunc
