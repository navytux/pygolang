# -*- coding: utf-8 -*-
# Copyright (C) 2018  Nexedi SA and Contributors.
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

from golang.gcompat import qq
from six import int2byte as bchr
from six.moves import range as xrange

def byterange(start, stop):
    b = b""
    for i in xrange(start, stop):
        b += bchr(i)

    return b

def test_qq():
    testv = (
        # in                want without leading/trailing "
        ('',                r""),

        (byterange(0,32),   r'\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f'),

        ('\'',              r"'"),
        ('"',               r"\""),
        ('ab c\ndef',       r"ab c\ndef"),
        ('a\'c\ndef',       r"a'c\ndef"),
        ('a\"c\ndef',       r"a\"c\ndef"),
        (u'a\"c\ndef',      u"a\\\"c\\ndef"),
        (b'a\"c\ndef',      r'a\"c\ndef'),
        ('привет\nмир',     r"привет\nмир"),
        (u'привет\nмир',    u"привет\\nмир"),

        # invalid utf-8
        (b"\xd0a",          r"\xd0a"),

        # non-printable utf-8
        (u"\u007f\u0080\u0081\u0082\u0083\u0084\u0085\u0086\u0087", u"\\x7f\\xc2\\x80\\xc2\\x81\\xc2\\x82\\xc2\\x83\\xc2\\x84\\xc2\\x85\\xc2\\x86\\xc2\\x87"),
    )

    for tin, twant in testv:
        twant = '"' + twant + '"'   # add lead/trail "
        assert qq(tin) == twant
