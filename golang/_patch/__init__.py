# -*- coding: utf-8 -*-
# Copyright (C) 2019-2020  Nexedi SA and Contributors.
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
"""Package _patch contains patch infrastructure and patches that Pygolang
applies automatically."""

from __future__ import print_function, absolute_import

from peak.util import imports   # thanks PJE
import sys

# `@afterimport(modname) def f(mod)` arranges for f to be called after when, if
# at all, module modname will be imported.
#
# modname must be top-level module.
def afterimport(modname):
    if '.' in modname:
        raise AssertionError("BUG: modname has dot: %r" % (modname,))
    def _(f):
        def patchmod(mod):
            #print('patching %s ...' % (modname,))
            f()

        # XXX on pypy < 7.3 lazy-loading fails: https://foss.heptapod.net/pypy/pypy/-/issues/3099
        #     -> import & patch eagerly
        if 'PyPy' in sys.version and sys.pypy_version_info < (7,3):
            try:
                mod = __import__(modname)
            except ImportError:
                return  # module not available - nothing to patch
            patchmod(mod)
            return

        imports.whenImported(modname, patchmod)
        return f
    return _
