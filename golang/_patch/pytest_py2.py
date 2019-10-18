# -*- coding: utf-8 -*-
# Copyright (C) 2019  Nexedi SA and Contributors.
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
"""pytest: py2: pygolang integration patches."""

from __future__ import print_function, absolute_import

from golang import _patch
import inspect

# _PY2 adds support for chained exceptions created by defer.
#
# It returns True by default (we are running under py2) except when called from
# _pytest/_code/code.FormattedExcinfo.repr_excinfo() for which it pretends to
# be running py3 if raised exception has .__cause__ .
class _PY2:
    @staticmethod
    def __nonzero__():
        fcall = inspect.currentframe().f_back
        if fcall.f_code.co_name != "repr_excinfo":
            return True     # XXX also check class/module?
        exci = fcall.f_locals.get('excinfo', None)
        if exci is None:
            return True
        exc = getattr(exci, 'value', None)
        if exc is None:
            return True
        if not hasattr(exc, '__cause__'):
            return True
        return False

@_patch.afterimport('_pytest')
def _():
    from _pytest._code import code
    code._PY2 = _PY2()
