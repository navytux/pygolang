# -*- coding: utf-8 -*-
# cython: language_level=2
# distutils: language=c++
#
# Copyright (C) 2021-2022  Nexedi SA and Contributors.
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

from golang cimport string, topyexc


# os_test.cpp
cdef extern from * nogil:
    """
    extern void __test_os_fileio_cpp(const golang::string&);
    extern void _test_os_pipe_cpp();
    """
    void __test_os_fileio_cpp(string)           except +topyexc
    void _test_os_pipe_cpp()                    except +topyexc
def _test_os_fileio_cpp(tmp_path):
    cdef string _tmpd = tmp_path
    with nogil:
        __test_os_fileio_cpp(_tmpd)
def test_os_pipe_cpp():
    with nogil:
        _test_os_pipe_cpp()
