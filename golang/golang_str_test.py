# -*- coding: utf-8 -*-
# Copyright (C) 2018-2022  Nexedi SA and Contributors.
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

from golang import b, u
from golang.gcompat import qq
from golang.strconv_test import byterange
from golang.golang_test import readfile, assertDoc, _pyrun, dir_testprog, PIPE
from pytest import raises
import sys
from six import text_type as unicode


# verify b, u
def test_strings():
    testv = (
        # bytes          <->            unicode
        (b'',                           u''),
        (b'hello',                      u'hello'),
        (b'hello\nworld',               u'hello\nworld'),
        (b'\xd0\xbc\xd0\xb8\xd1\x80',   u'мир'),

        # invalid utf-8
        (b'\xd0',                       u'\udcd0'),
        (b'a\xd0b',                     u'a\udcd0b'),
        # invalid utf-8 with byte < 0x80
        (b'\xe2\x28\xa1',               u'\udce2(\udca1'),

        # more invalid utf-8
        # https://stackoverflow.com/questions/1301402/example-invalid-utf8-string
        (b"\xc3\x28",                   u'\udcc3('),        # Invalid 2 Octet Sequence
        (b"\xa0\xa1",                   u'\udca0\udca1'),   # Invalid Sequence Identifier
        (b"\xe2\x82\xa1",               u'\u20a1'),         # Valid 3 Octet Sequence '₡'
        (b"\xe2\x28\xa1",               u'\udce2(\udca1'),  # Invalid 3 Octet Sequence (in 2nd Octet)
        (b"\xe2\x82\x28",               u'\udce2\udc82('),  # Invalid 3 Octet Sequence (in 3rd Octet)
        (b"\xf0\x90\x8c\xbc",           u'\U0001033c'),     # Valid 4 Octet Sequence '𐌼'
        (b"\xf0\x28\x8c\xbc",           u'\udcf0(\udc8c\udcbc'), # Invalid 4 Octet Sequence (in 2nd Octet)
        (b"\xf0\x90\x28\xbc",           u'\udcf0\udc90(\udcbc'), # Invalid 4 Octet Sequence (in 3rd Octet)
        (b"\xf0\x28\x8c\x28",           u'\udcf0(\udc8c('), # Invalid 4 Octet Sequence (in 4th Octet)
        (b"\xf8\xa1\xa1\xa1\xa1",                           # Valid 5 Octet Sequence (but not Unicode!)
                                        u'\udcf8\udca1\udca1\udca1\udca1'),
        (b"\xfc\xa1\xa1\xa1\xa1\xa1",                       # Valid 6 Octet Sequence (but not Unicode!)
                                        u'\udcfc\udca1\udca1\udca1\udca1\udca1'),

        # surrogate
        (b'\xed\xa0\x80',               u'\udced\udca0\udc80'),

        # x00 - x1f
        (byterange(0,32),
         u"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f" +
         u"\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f"),

        # non-printable utf-8
        (b'\x7f\xc2\x80\xc2\x81\xc2\x82\xc2\x83\xc2\x84\xc2\x85\xc2\x86\xc2\x87',
                                        u"\u007f\u0080\u0081\u0082\u0083\u0084\u0085\u0086\u0087"),

        # some characters with U >= 0x10000
        (b'\xf0\x9f\x99\x8f',           u'\U0001f64f'),    # 🙏
        (b'\xf0\x9f\x9a\x80',           u'\U0001f680'),    # 🚀
    )

    for tbytes, tunicode in testv:
        assert b(tbytes)   == tbytes
        assert u(tunicode) == tunicode

        assert b(tunicode) == tbytes
        assert u(tbytes)   == tunicode

        assert b(u(tbytes))     == tbytes
        assert u(b(tunicode))   == tunicode


    # invalid types
    with raises(TypeError): b(1)
    with raises(TypeError): u(1)
    with raises(TypeError): b(object())
    with raises(TypeError): u(object())

    # TODO also handle bytearray?

    # b(b(·)) = identity
    _ = b(u'миру мир 123')
    assert isinstance(_, bytes)
    assert b(_) is _

    # u(u(·)) = identity
    _ = u(u'мир труд май')
    assert isinstance(_, unicode)
    assert u(_) is _

# verify print for _pystr and _pyunicode
def test_strings_print():
    outok = readfile(dir_testprog + "/golang_test_str.txt")
    retcode, stdout, stderr = _pyrun(["golang_test_str.py"],
                                cwd=dir_testprog, stdout=PIPE, stderr=PIPE)
    assert retcode == 0, (stdout, stderr)
    assert stderr == b""
    assertDoc(outok, stdout)


def test_qq():
    # NOTE qq is also tested as part of strconv.quote

    # qq(any) returns string type
    assert isinstance(qq(b('мир')), str)    # qq(b) -> str (bytes·py2, unicode·py3)
    assert isinstance(qq( u'мир'),  str)    # qq(u) -> str (bytes·py2, unicode·py3)

    # however what qq returns can be mixed with both unicode and bytes
    assert b'hello %s !' % qq(b('мир')) == b('hello "мир" !')   # b % qq(b)
    assert b'hello %s !' % qq(u('мир')) == b('hello "мир" !')   # b % qq(u) -> b
    assert u'hello %s !' % qq(u('мир')) == u('hello "мир" !')   # u % qq(u)
    assert u'hello %s !' % qq(b('мир')) ==  u'hello "мир" !'    # u % qq(b) -> u

    # custom attributes cannot be injected to what qq returns
    x = qq('мир')
    if not ('PyPy' in sys.version): # https://foss.heptapod.net/pypy/pypy/issues/2763
        with raises(AttributeError):
            x.hello = 1
