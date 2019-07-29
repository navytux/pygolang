# -*- coding: utf-8 -*-
# cython: language_level=2
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

# XXX golang._golang -> golang ?
from golang._golang cimport chan, select, _send, _recv, _recv_, _default
from golang._golang cimport _chanselect     # XXX temp?
from libc.stdio cimport printf

cdef extern from *:
    ctypedef bint cbool "bool"

cdef void _test_chan_nogil() nogil:
    cdef chan[int] a
    cdef chan[char[100]] b
    cdef int i=1, j
    cdef char[100] s
    cdef cbool jok

    _ = _chanselect([
        _send(a, &i),           # 0
        _recv(b, &s),           # 1
        _recv_(a, &j, &jok),    # 2
        _default,               # 3
    ], 4)

    """
    _ = select({
        _send(a, &i),           # 0
        _recv(b, &s),           # 1
        _recv_(a, &j, &jok),    # 2
        _default,               # 3
    })
    """

    if _ == 0:
        printf('tx\n')
    if _ == 1:
        printf('rx\n')
    if _ == 2:
        printf('defaut\n')


def test_chan_nogil():
    with nogil:
        _test_chan_nogil()
