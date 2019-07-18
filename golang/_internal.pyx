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
"""Package _internal provides unsafe bits that are internally used by package golang"""

from libc.stdio cimport printf

# bytepatch does `mem[i]=b` even for read-only mem object such as bytes.
def _bytepatch(const unsigned char[::1] mem not None, int i, unsigned char b):
    # we don't care if its readonly or writeable buffer - we change it anyway
    cdef unsigned char *xmem = <unsigned char *>&mem[0]
    assert 0 <= i < len(mem)
    #printf(" mem: <- %i %i %i %i\n",  mem[0],  mem[1],  mem[2],  mem[3])
    #printf("xmem: <- %i %i %i %i\n", xmem[0], xmem[1], xmem[2], xmem[3])
    xmem[i] = b
    #printf("xmem: -> %i %i %i %i\n", xmem[0], xmem[1], xmem[2], xmem[3])
    #printf(" mem: -> %i %i %i %i\n",  mem[0],  mem[1],  mem[2],  mem[3])

def bytepatch(mem, i, b):
    #print()
    #print('bytepatch <- %r  @%d = %r' % (mem, i, b))
    _bytepatch(mem, i, b)
    #print('bytepatch -> %r' % (mem,))
