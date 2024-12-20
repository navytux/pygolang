# -*- coding: utf-8 -*-
# Copyright (C) 2023-2024  Nexedi SA and Contributors.
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
"""_golang_str_pickle.pyx complements _golang_str.pyx and keeps everything
related to pickling strings.

It is included from _golang_str.pyx .
"""

if PY_MAJOR_VERSION >= 3:
    import copyreg as pycopyreg
else:
    import copy_reg as pycopyreg


# support for pickling bstr/ustr as standalone types.
cdef _bstr__reduce_ex__(self, protocol):
    # override reduce for protocols < 2. Builtin handler for that goes through
    # copyreg._reduce_ex which eventually calls bytes(bstr-instance) to
    # retrieve state, which gives bstr, not bytes. Fix state to be bytes ourselves.
    if protocol >= 2:
        return zbytes.__reduce_ex__(self, protocol)
    return (
        pycopyreg._reconstructor,
        (self.__class__, self.__class__, _bdata(self))
    )

cdef _ustr__reduce_ex__(self, protocol):
    # override reduce for protocols < 2. Builtin handler for that goes through
    # copyreg._reduce_ex which eventually calls unicode(ustr-instance) to
    # retrieve state, which gives ustr, not unicode. Fix state to be unicode ourselves.
    if protocol >= 2:
        return zunicode.__reduce_ex__(self, protocol)
    return (
        pycopyreg._reconstructor,
        (self.__class__, self.__class__, _udata(self))
    )
