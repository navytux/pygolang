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
"""Package pyx/runtime.pyx complements golang.pyx and provides support for
Python/Cython runtimes that can be used from nogil code.

 - `PyFunc` represents Python function that can be called from nogil code.
"""

from cpython cimport PyObject


cdef extern from "golang/pyx/runtime.h" namespace "golang::pyx::runtime" nogil:
    cppclass PyFunc:
        __init__(PyObject *pyf)
        void operator() ()
