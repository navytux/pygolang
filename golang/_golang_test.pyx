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

from libc.stdio cimport printf

cdef void test() nogil:
    cdef chan a, b
    cdef void *tx = NULL
    cdef void *rx = NULL
    cdef int _

    cdef selcase sel[3]
    sel[0].op   = chansend      XXX -> _selsend     + test via _send/_recv
    sel[0].data = tx
    sel[1].op   = chanrecv          -> _selrecv
    sel[1].data = rx
    sel[2].op   = default
    _ = chanselect(sel, 3)  # XXX 3 -> array_len(sel)

    if _ == 0:
        printf('tx\n')
    if _ == 1:
        printf('rx\n')
    if _ == 2:
        printf('defaut\n')


def xtest():
    with nogil:
        test()
