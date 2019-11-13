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
"""Package cxx provides C++ amendments to be used by libgolang and its users."""

cimport libcpp.unordered_map
cimport libcpp.unordered_set

cdef extern from "<golang/cxx.h>" namespace "golang::cxx" nogil:
    cppclass dict[Key, Value] (libcpp.unordered_map.unordered_map[Key, Value]):
        bint has(Key k) const
        # TODO get
        # TODO pop

    cppclass set[Key] (libcpp.unordered_set.unordered_set[Key]):
        bint has(Key k) const
