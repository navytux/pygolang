# -*- coding: utf-8 -*-
# Copyright (C) 2018-2023  Nexedi SA and Contributors.
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

from golang import bstr
from golang.strconv import quote, unquote, unquote_next
from golang.gcompat import qq

from six import int2byte as bchr
from six.moves import range as xrange
from pytest import raises, mark

import codecs


def byterange(start, stop):
    b = b""
    for i in xrange(start, stop):
        b += bchr(i)

    return b

def assert_bstreq(x, y):
    assert type(x) is bstr
    assert x == y

def test_quote():
    testv = (
        # in                quoted without leading/trailing "
        ('',                r""),

        (byterange(0,32),   br'\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f'),

        ('\'',              r"'"),
        ('"',               r"\""),
        ('ab c\ndef',       r"ab c\ndef"),
        ('a\'c\ndef',       r"a'c\ndef"),
        ('a\"c\ndef',       r"a\"c\ndef"),
        (u'a\"c\ndef',      u"a\\\"c\\ndef"),
        (b'a\"c\ndef',      br'a\"c\ndef'),
        ('привет\nмир',     r"привет\nмир"),
        (u'привет\nмир',    u"привет\\nмир"),

        # invalid utf-8
        (b"\xd0a",          br"\xd0a"),

        # non-printable utf-8
        (u"\u007f\u0080\u0081\u0082\u0083\u0084\u0085\u0086\u0087", u"\\x7f\\xc2\\x80\\xc2\\x81\\xc2\\x82\\xc2\\x83\\xc2\\x84\\xc2\\x85\\xc2\\x86\\xc2\\x87"),

        # invalid rune
        (u'\ufffd',         u'�'),
    )

    # quote/unquote* always give bstr
    BEQ = assert_bstreq

    for tin, tquoted in testv:
        # quote(in) == quoted
        # in = unquote(quoted)
        q = b'"' if isinstance(tquoted, bytes) else '"'
        tail = b'123' if isinstance(tquoted, bytes) else '123'
        tquoted = q + tquoted + q   # add lead/trail "

        BEQ(quote(tin), tquoted)
        BEQ(unquote(tquoted), tin)
        _, __ = unquote_next(tquoted);          BEQ(_, tin);  BEQ(__, "")
        _, __ = unquote_next(tquoted + tail);   BEQ(_, tin);  BEQ(__, tail)
        with raises(ValueError): unquote(tquoted + tail)

        BEQ(qq(tin), tquoted)

        # also check how it works on complementary unicode/bytes input type
        if isinstance(tin, bytes):
            try:
                tin = tin.decode('utf-8')
            except UnicodeDecodeError:
                # some inputs are not valid UTF-8
                continue
            tquoted = tquoted.decode('utf-8')
            tail = tail.decode('utf-8')
        else:
            # tin was unicode
            tin = tin.encode('utf-8')
            tquoted = tquoted.encode('utf-8')
            tail = tail.encode('utf-8')

        BEQ(quote(tin), tquoted)
        BEQ(unquote(tquoted), tin)
        _, __ = unquote_next(tquoted);          BEQ(_, tin);  BEQ(__, "")
        _, __ = unquote_next(tquoted + tail);   BEQ(_, tin);  BEQ(__, tail)
        with raises(ValueError): unquote(tquoted + tail)

        BEQ(qq(tin), tquoted)


# verify that non-canonical quotation can be unquoted too.
def test_unquote_noncanon():
    testv = (
        # quoted w/o "      unquoted
        (r'\a',             "\x07"),
        (r'\b',             "\x08"),
        (r'\v',             "\x0b"),
        (r'\f',             "\x0c"),
    )

    for tquoted, tunquoted in testv:
        q = '"' + tquoted + '"'
        assert unquote(q) == tunquoted


def test_unquote_bad():
    testv = (
        # in            error
        ('x"zzz"',      'no starting "'),
        ('"zzz',        'no closing "'),
        ('"\\',         'unexpected EOL after \\'),
        ('"\\x',        'unexpected EOL after \\x'),
        ('"\\x0',       'unexpected EOL after \\x'),
        ('"\\z"',       'invalid escape \\z'),
    )

    for tin, err in testv:
        with raises(ValueError) as exc:
            unquote(tin)
        assert exc.value.args == (err,)


# ---- benchmarks ----

# quoting + unquoting
uchar_testv = ['a',               # ascii
               u'α',              # 2-bytes utf8
               u'\u65e5',         # 3-bytes utf8
               u'\U0001f64f']     # 4-bytes utf8

@mark.parametrize('ch', uchar_testv)
def bench_quote(b, ch):
    s = bstr_ch1000(ch)
    q = quote
    for i in xrange(b.N):
        q(s)

def bench_stdquote(b):
    s = b'a'*1000
    q = repr
    for i in xrange(b.N):
        q(s)


@mark.parametrize('ch', uchar_testv)
def bench_unquote(b, ch):
    s = bstr_ch1000(ch)
    s = quote(s)
    unq = unquote
    for i in xrange(b.N):
        unq(s)

def bench_stdunquote(b):
    s = b'"' + b'a'*1000 + b'"'
    escape_decode = codecs.escape_decode
    def unq(s): return escape_decode(s[1:-1])[0]
    for i in xrange(b.N):
        unq(s)


# bstr_ch1000 returns bstr with many repetitions of character ch occupying ~ 1000 bytes.
def bstr_ch1000(ch): # -> bstr
    assert len(ch) == 1
    s = bstr(ch)
    s = s * (1000 // len(s))
    if len(s) % 3 == 0:
        s += 'x'
    assert len(s) == 1000
    return s
