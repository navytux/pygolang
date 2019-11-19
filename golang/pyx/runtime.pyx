# cython: language_level=2
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

# pyx/runtime.pyx implementation - see pyx/runtime.pxd for package overview.

from __future__ import print_function, absolute_import

# initialize libpyxruntime at import time.
# NOTE golang.pyx imports us right after initializing libgolang.

import atexit as pyatexit

cdef extern from "golang/pyx/runtime.h" namespace "golang::pyx::runtime" nogil:
    void _init()
    void _pyatexit_nogil()

# init libpyxruntime
_init()

# register its pyatexit hook
cdef void _pyatexit():
    with nogil:
        _pyatexit_nogil()

pyatexit.register(_pyatexit)
