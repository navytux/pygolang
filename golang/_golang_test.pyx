# -*- coding: utf-8 -*-
# cython: language_level=2
# distutils: language=c++
# Copyright (C) 2018-2019  Nexedi SA and Contributors.
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

from golang cimport chan, makechan, select, _send, _recv, _recv_, _default, panic, topyexc
from libc.stdio cimport printf

# small test that verifies pyx-level channel API.
# the work of channels themselves is thoroughly excersized in golang_test.py

cdef extern from *:
    ctypedef bint cbool "bool"

ctypedef struct Point:
    int x
    int y

#cdef void zzz() nogil except +:
#    makechan[int](1)
#    #printf("hello world\n")



cdef void __test_chan_nogil() nogil except +topyexc:
    cdef chan[int]   chi = makechan[int](1)
    cdef chan[Point] chp # nil
    cdef int i, j
    cdef Point p
    cdef cbool jok

    i=+1; chi.send(&i)
    j=-1; chi.recv(&j)
    if j == i:
        panic("send -> recv != I")

    _ = select([
        _send(chi, &i),         # 0
        _recv(chp, &p),         # 1
        _recv_(chi, &j, &jok),  # 2
        _default,               # 3
    ])

    if _ == 0:
        printf('tx\n')
    if _ == 1:
        printf('rx\n')
    if _ == 2:
        printf('rx_\n')
    if _ == 3:
        printf('default\n')

## XXX cannot add `except +topyexc` to ^^^ __test_chan_nogil
#cdef void _test_chan_nogil() nogil except +topyexc:
#    __test_chan_nogil()

def test_chan_nogil():
    with nogil:
        __test_chan_nogil()

# golang_test_c.c
cdef extern from *:
    """
    extern "C" void _test_chan_c();
    """
    void _test_chan_c() nogil except +topyexc
def test_chan_c():
    with nogil:
        _test_chan_c()

# golang_test_cpp.cpp
cdef extern from *:
    """
    extern void _test_chan_cpp();
    """
    void _test_chan_cpp() nogil except +topyexc
def test_chan_cpp():
    with nogil:
        _test_chan_cpp()
