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

from golang._internal import bytepatch


def test_bytepatch():
    #b = b'\x00\x01\x02\x03'
    b = bytearray(b'\x00\x01\x02\x03')
    assert b[1:2] == b'\x01'
    bytepatch(b, 1, 0x23)
    bytepatch(b, 1, 0x23)
    bb = bytes(b)
    bytepatch(bb, 2, 0x32)
    print(bb)
    assert bb[1:2] == b'\x23'
    assert bb[2:3] == b'\x32'   # XXX breaks on pypy3 (but works on pypy2 and cpython2 & 3)
