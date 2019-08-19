# cython: language_level=2
# distutils: language=c++
#
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

# Small program that uses a bit of golang.pyx nogil features, mainly to verify
# that external project can build against golang in pyx mode.

from golang cimport go, chan, makechan, topyexc
from libc.stdio cimport printf

cdef nogil:

    void worker(chan[int] ch, int i, int j):
        ch.send(i*j)

    void _main() except +topyexc:
        cdef chan[int] ch = makechan[int]()
        cdef int i
        for i in range(3):
            go(worker, ch, i, 4)

        for i in range(3):
            ch.recv()

        ch.close()
        #_, ok = ch.recv_() # TODO teach Cython to coerce pair[X,Y] -> (X,Y)
        ch.recv_()

        printf("test.pyx: OK\n")

def main():
    _main()
