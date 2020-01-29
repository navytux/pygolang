# -*- coding: utf-8 -*-
# cython: language_level=2
# distutils: language=c++
#
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

from __future__ import print_function, absolute_import

from golang cimport topyexc

# strings_test.cpp
cdef extern from * nogil:
    """
    extern void _test_strings_has_prefix();
    extern void _test_strings_trim_prefix();
    extern void _test_strings_has_suffix();
    extern void _test_strings_trim_suffix();
    extern void _test_strings_split();
    """
    void _test_strings_has_prefix()             except +topyexc
    void _test_strings_trim_prefix()            except +topyexc
    void _test_strings_has_suffix()             except +topyexc
    void _test_strings_trim_suffix()            except +topyexc
    void _test_strings_split()                  except +topyexc
def test_strings_has_prefix():
    with nogil:
        _test_strings_has_prefix()
def test_strings_trim_prefix():
    with nogil:
        _test_strings_trim_prefix()
def test_strings_has_suffix():
    with nogil:
        _test_strings_has_suffix()
def test_strings_trim_suffix():
    with nogil:
        _test_strings_trim_suffix()
def test_strings_split():
    with nogil:
        _test_strings_split()
