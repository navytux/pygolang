# -*- coding: utf-8 -*-
# cython: language_level=2
# cython: c_string_type=str, c_string_encoding=utf8
# cython: legacy_implicit_noexcept=True
# distutils: language=c++
#
# Copyright (C) 2020-2025  Nexedi SA and Contributors.
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

from golang cimport error, pyerror, nil, topyexc
from golang cimport errors, fmt


# pyerror_mkchain creates error chain from [] of text.
def pyerror_mkchain(textv):
    cdef error err
    cdef const char *s
    for text in reversed(textv):
        if err == nil:
            err = errors.New(text)
        else:
            s = text
            err = fmt.errorf("%s: %w", s, err)
    return pyerror.from_error(err)


# errors_test.cpp
cdef extern from * nogil:
    """
    extern void _test_errors_new_cpp();
    extern void _test_errors_unwrap_cpp();
    extern void _test_errors_is_cpp();
    """
    void _test_errors_new_cpp()                 except +topyexc
    void _test_errors_unwrap_cpp()              except +topyexc
    void _test_errors_is_cpp()                  except +topyexc

def test_errors_new_cpp():
    with nogil:
        _test_errors_new_cpp()
def test_errors_unwrap_cpp():
    with nogil:
        _test_errors_unwrap_cpp()
def test_errors_is_cpp():
    with nogil:
        _test_errors_is_cpp()
