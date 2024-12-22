# -*- coding: utf-8 -*-
# Copyright (C) 2018-2024  Nexedi SA and Contributors.
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

import golang
from golang import b, u, bstr, ustr, biter, uiter, bbyte, uchr, func, defer, panic
from golang._golang import _udata, _bdata
from golang.gcompat import qq
from golang.strconv_test import byterange
from golang.golang_test import readfile, assertDoc, _pyrun, dir_testprog, PIPE
from pytest import raises, mark, skip, xfail
import _testcapi as testcapi
import sys
import six
from six import text_type as unicode, unichr
from six.moves import range as xrange
import gc, re, pickle, copy, types
import array, collections


# buftypes lists types with buffer interface that we will test against.
#
# NOTE bytearray is not included here - being bytes-like object it is handled
# and tested explicitly in tests that exercise interaction of bstr/ustr with
# bytes/unicode and bytearray.
buftypes = [
        memoryview,
        lambda x: array.array('B', x),
]
if six.PY2:
    buftypes.append(buffer) # no buffer on py3


# verify b/u and bstr/ustr basics.
def test_strings_basic():
    # UTF-8 encode/decode
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

        # invalid rune
        (b'\xef\xbf\xbd',               u'�'),
    )

    for tbytes, tunicode in testv:
        assert type(tbytes)   is bytes
        assert type(tunicode) is unicode

        # b(bytes), u(unicode)
        b_tbytes    = b(tbytes);            assert type(b_tbytes)    is bstr
        b_tbytes_   = _bdata(b_tbytes);     assert type(b_tbytes_)   is bytes
        u_tunicode  = u(tunicode);          assert type(u_tunicode)  is ustr
        u_tunicode_ = _udata(u_tunicode);   assert type(u_tunicode_) is unicode
        assert b_tbytes_   == tbytes
        assert u_tunicode_ == tunicode

        # b(unicode), u(bytes)
        b_tunicode  = b(tunicode);          assert type(b_tunicode)  is bstr
        b_tunicode_ = _bdata(b_tunicode);   assert type(b_tunicode_) is bytes
        u_tbytes    = u(tbytes);            assert type(u_tbytes)    is ustr
        u_tbytes_   = _udata(u_tbytes);     assert type(u_tbytes_)   is unicode
        assert b_tunicode_ == tbytes
        assert u_tbytes_   == tunicode

        # b(u(bytes)),  u(b(unicode))
        bu_tbytes   = b(u(tbytes));         assert type(bu_tbytes)   is bstr
        bu_tbytes_  = _bdata(bu_tbytes);    assert type(bu_tbytes_)  is bytes
        ub_tunicode = u(b(tunicode));       assert type(ub_tunicode) is ustr
        ub_tunicode_= _udata(ub_tunicode);  assert type(ub_tunicode_)is unicode
        assert bu_tbytes_   == tbytes
        assert ub_tunicode_ == tunicode


    # b/u accept only ~bytes/~unicode/bytearray/buffer
    with raises(TypeError): b()
    with raises(TypeError): u()
    with raises(TypeError): b(123)
    with raises(TypeError): u(123)
    with raises(TypeError): b([1,'β'])
    with raises(TypeError): u([1,'β'])
    with raises(TypeError): b(object())
    with raises(TypeError): u(object())

    # bstr/ustr - similarly to str - accept arbitrary objects
    _ = bstr();         assert type(_) is bstr;  assert _ == ''
    _ = ustr();         assert type(_) is ustr;  assert _ == ''
    _ = bstr(123);      assert type(_) is bstr;  assert _ == '123'
    _ = ustr(123);      assert type(_) is ustr;  assert _ == '123'
    _ = bstr([1,'β']);  assert type(_) is bstr;  assert _ == "[1, 'β']"
    _ = ustr([1,'β']);  assert type(_) is ustr;  assert _ == "[1, 'β']"
    obj = object()
    _ = bstr(obj);      assert type(_) is bstr;  assert _ == str(obj)  # <object ...>
    _ = ustr(obj);      assert type(_) is ustr;  assert _ == str(obj)  # <object ...>

    # when stringifying they also handle bytes/bytearray inside containers as UTF-8 strings
    _ = bstr([xunicode(  'β')]);   assert type(_) is bstr;  assert _ == "['β']"
    _ = ustr([xunicode(  'β')]);   assert type(_) is ustr;  assert _ == "['β']"
    _ = bstr([xbytes(    'β')]);   assert type(_) is bstr;  assert _ == "['β']"
    _ = ustr([xbytes(    'β')]);   assert type(_) is ustr;  assert _ == "['β']"
    _ = bstr([xbytearray('β')]);   assert type(_) is bstr;  assert _ == "['β']"
    _ = ustr([xbytearray('β')]);   assert type(_) is ustr;  assert _ == "['β']"


    b_  = xbytes    ("мир");  assert type(b_) is bytes
    u_  = xunicode  ("мир");  assert type(u_) is unicode
    ba_ = xbytearray("мир");  assert type(ba_) is bytearray

    # b/u from unicode
    bs = b(u_);    assert isinstance(bs, bytes);    assert type(bs) is bstr
    us = u(u_);    assert isinstance(us, unicode);  assert type(us) is ustr
    _ = bstr(u_);  assert type(_) is bstr;  assert _ == "мир"
    _ = ustr(u_);  assert type(_) is ustr;  assert _ == "мир"

    # b/u from bytes
    _ = b(b_);     assert type(_) is bstr;  assert _ == "мир"
    _ = u(b_);     assert type(_) is ustr;  assert _ == "мир"
    _ = bstr(b_);  assert type(_) is bstr;  assert _ == "мир"
    _ = ustr(b_);  assert type(_) is ustr;  assert _ == "мир"

    # b/u from bytearray
    _ = b(ba_);    assert type(_) is bstr;  assert _ == "мир"
    _ = u(ba_);    assert type(_) is ustr;  assert _ == "мир"
    _ = bstr(ba_); assert type(_) is bstr;  assert _ == "мир"
    _ = ustr(ba_); assert type(_) is ustr;  assert _ == "мир"

    # b/u from buffer
    for tbuf in buftypes:
        bbuf_ = tbuf(b_)
        bbuf_std_str = str(bbuf_)   # e.g. '<memory at ...>' for memoryview
        _ = b(bbuf_);    assert type(_) is bstr;  assert _ == "мир"
        _ = u(bbuf_);    assert type(_) is ustr;  assert _ == "мир"
        _ = bstr(bbuf_); assert type(_) is bstr;  assert _ == bbuf_std_str # NOTE not 'мир'
        _ = ustr(bbuf_); assert type(_) is ustr;  assert _ == bbuf_std_str

    # bstr/ustr from bytes/bytearray/buffer with encoding
    k8mir_bytes = u"мир".encode('koi8-r')
    for tbuf in [bytes, bytearray] + buftypes:
        k8mir = tbuf(k8mir_bytes)
        _ = bstr(k8mir, 'koi8-r');  assert type(_) is bstr;  assert _ == "мир"
        _ = ustr(k8mir, 'koi8-r');  assert type(_) is ustr;  assert _ == "мир"
        with raises(UnicodeDecodeError): bstr(k8mir, 'ascii')
        with raises(UnicodeDecodeError): ustr(k8mir, 'ascii')
        _ = bstr(k8mir, 'ascii', 'replace');  assert type(_) is bstr;  assert _ == u'\ufffd\ufffd\ufffd'
        _ = ustr(k8mir, 'ascii', 'replace');  assert type(_) is ustr;  assert _ == u'\ufffd\ufffd\ufffd'
        # no encoding -> utf8 with surrogateescape for bytes/bytearray,  stringify for the rest
        k8mir_usurrogateescape = u'\udccd\udcc9\udcd2'
        k8mir_strok = k8mir_usurrogateescape
        if not tbuf in (bytes, bytearray):
            k8mir_strok = str(k8mir)  # e.g. '<memory at ...>' for memoryview
        _ = bstr(k8mir);  assert type(_) is bstr;  assert _ == k8mir_strok
        _ = ustr(k8mir);  assert type(_) is ustr;  assert _ == k8mir_strok
        _ = b   (k8mir);  assert type(_) is bstr;  assert _ == k8mir_usurrogateescape # always surrogateescape
        _ = u   (k8mir);  assert type(_) is ustr;  assert _ == k8mir_usurrogateescape
        # encoding specified -> treat it precisely
        with raises(UnicodeDecodeError): bstr(k8mir, 'utf-8')
        with raises(UnicodeDecodeError): ustr(k8mir, 'utf-8')
        with raises(UnicodeDecodeError): bstr(k8mir, encoding='utf-8')
        with raises(UnicodeDecodeError): ustr(k8mir, encoding='utf-8')
        with raises(UnicodeDecodeError): bstr(k8mir, errors='strict')
        with raises(UnicodeDecodeError): ustr(k8mir, errors='strict')


    # b(b(·)) = identity,   u(u(·)) = identity
    assert b(bs) is bs;  assert bstr(bs) is bs
    assert u(us) is us;  assert ustr(us) is us

    # unicode(u(·)) = identity
    assert unicode(us) is us

    # unicode(b) -> u
    _ = unicode(bs);  assert type(_) is ustr;  assert _ == "мир"

    # bytes(b|u) -> bytes
    _ = bytes(bs);  assert type(_) is x32(bytes, bstr);  assert _ == b'\xd0\xbc\xd0\xb8\xd1\x80'
    _ = bytes(us);  assert type(_) is x32(bytes, bstr);  assert _ == b'\xd0\xbc\xd0\xb8\xd1\x80'

    # bytearray(b|u) -> bytearray
    _ = bytearray(bs);  assert type(_) is bytearray;  assert _ == b'\xd0\xbc\xd0\xb8\xd1\x80'
    _ = bytearray(us);  assert type(_) is bytearray;  assert _ == b'\xd0\xbc\xd0\xb8\xd1\x80'

    # b(u(·)), u(b(·))
    _ = b(us);    assert type(_) is bstr;  assert _ == "мир"
    _ = u(bs);    assert type(_) is ustr;  assert _ == "мир"
    _ = bstr(us); assert type(_) is bstr;  assert _ == "мир"
    _ = ustr(bs); assert type(_) is ustr;  assert _ == "мир"

    # hash of b/u is made to be equal to hash of current str
    # (it cannot be equal to hash(b'мир') and hash(u'мир') at the same time as those hashes differ)
    assert hash(us) == hash("мир");  assert us == "мир"
    assert hash(bs) == hash("мир");  assert bs == "мир"

    # str/repr
    _ = str(us);   assert isinstance(_, str);  assert _ == "мир"
    _ = str(bs);   assert isinstance(_, str);  assert _ == "мир"
    _ = repr(us);  assert isinstance(_, str);  assert _ == "u('мир')"
    _ = repr(bs);  assert isinstance(_, str);  assert _ == "b('мир')"

    # str/repr of non-valid utf8
    b_hik8 = xbytes  ('привет ')+b(k8mir_bytes);  assert type(b_hik8) is bstr
    u_hik8 = xunicode('привет ')+u(k8mir_bytes);  assert type(u_hik8) is ustr
    assert _bdata(b_hik8) == b'\xd0\xbf\xd1\x80\xd0\xb8\xd0\xb2\xd0\xb5\xd1\x82 \xcd\xc9\xd2'
    assert _udata(u_hik8) == u'привет \udccd\udcc9\udcd2'

    _ = str(u_hik8);   assert isinstance(_, str);  assert _ == xbytes('привет ')+b'\xcd\xc9\xd2'
    _ = str(b_hik8);   assert isinstance(_, str);  assert _ == xbytes('привет ')+b'\xcd\xc9\xd2'
    _ = repr(u_hik8);  assert isinstance(_, str);  assert _ == r"u(b'привет \xcd\xc9\xd2')"
    _ = repr(b_hik8);  assert isinstance(_, str);  assert _ == r"b(b'привет \xcd\xc9\xd2')"

    # str/repr of quotes
    def _(text, breprok, ureprok):
        bt = b(text);  assert type(bt) is bstr
        ut = u(text);  assert type(ut) is ustr
        _ = str(bt);   assert isinstance(_, str);  assert _ == text
        _ = str(ut);   assert isinstance(_, str);  assert _ == text
        _ = repr(bt);  assert isinstance(_, str);  assert _ == breprok
        _ = repr(ut);  assert isinstance(_, str);  assert _ == ureprok
    _('',           "b('')",                "u('')")
    _('"',          "b('\"')",              "u('\"')")
    _("'",          'b("\'")',              'u("\'")')
    _('"\'',        "b('\"\\'')",           "u('\"\\'')")
    _('"α" \'β\'',  "b('\"α\" \\'β\\'')",   "u('\"α\" \\'β\\'')")

    # custom attributes cannot be injected to bstr/ustr
    if not ('PyPy' in sys.version): # https://foss.heptapod.net/pypy/pypy/issues/2763
        with raises(AttributeError):
            us.hello = 1
        with raises(AttributeError):
            bs.hello = 1


# verify that bstr/ustr are created with correct refcount.
def test_strings_refcount():
    # buffer with string data - not bytes nor unicode so that when builtin
    # string types are patched there is no case where bytes is created from the
    # same bytes, or unicode is created from the same unicode - only increasing
    # refcount of original object.
    data = bytearray([ord('a'), ord('b'), ord('c'), ord('4')])

    # first verify our logic on std type
    obj = bytes(data);      assert type(obj) is bytes
    gc.collect();   assert sys.getrefcount(obj) == 1+1   # +1 due to obj passed to getrefcount call

    # bstr
    obj = b(data);          assert type(obj) is bstr
    gc.collect();           assert sys.getrefcount(obj) == 1+1
    obj = bstr(data);       assert type(obj) is bstr
    gc.collect();           assert sys.getrefcount(obj) == 1+1

    # ustr
    obj = u(data);          assert type(obj) is ustr
    gc.collect();           assert sys.getrefcount(obj) == 1+1
    obj = ustr(data);       assert type(obj) is ustr
    gc.collect();           assert sys.getrefcount(obj) == 1+1


# verify memoryview(bstr|ustr).
def test_strings_memoryview():
    bs = b('мир')
    us = u('май')

    with raises(TypeError):
        memoryview(us)

    m = memoryview(bs)
    assert len(m) == 6
    def _(i): # returns m[i] as int
        x = m[i]
        if six.PY2: # on py2 memoryview[i] returns bytechar
            x = ord(x)
        return x
    assert _(0) == 0xd0
    assert _(1) == 0xbc
    assert _(2) == 0xd0
    assert _(3) == 0xb8
    assert _(4) == 0xd1
    assert _(5) == 0x80


# verify that ord on bstr/ustr works as expected.
def test_strings_ord():
    with raises(TypeError): ord(b(''))
    with raises(TypeError): ord(u(''))
    with raises(TypeError): ord(b('ab'))
    with raises(TypeError): ord(u('ab'))
    assert ord(b('a')) == 97
    assert ord(u('a')) == 97
    with raises(TypeError): ord(b('м'))     # 2 bytes, not 1
    assert ord(u('м')) == 1084

    for i in range(0x100):
        bc = b(bytearray([i]))
        assert len(bc) == 1
        assert ord(bc) == i

    for i in range(0x10000):
        uc = u(unichr(i))
        assert len(uc) == 1
        assert ord(uc) == i

# verify bbyte.
def test_strings_bbyte():
    with raises(ValueError): bbyte(-1)
    with raises(ValueError): bbyte(0x100)
    for i in range(0x100):
        bi = bbyte(i)
        assert type(bi) is bstr
        assert len(bi)  == 1
        assert ord(bi)  == i
        assert bi == bytearray([i])

# verify uchr.
def test_strings_uchr():
    with raises(ValueError): unichr(-1)
    # upper limit depends on whether python was built with ucs as 2-bytes or 4-bytes long
    # but at least it all should work for small 2-bytes range
    for i in range(0x10000):
        ui = uchr(i)
        assert type(ui) is ustr
        assert len(ui)  == 1
        assert ord(ui)  == i
        assert ui == unichr(i)


# verify strings access by index.
def test_strings_index():
    us = u("миру мир"); u_ = u"миру мир"
    bs = b("миру мир"); b_ = xbytes("миру мир")

    assert len(us) == 8;   assert len(u_) == 8
    assert len(bs) == 15;  assert len(b_) == 15

    # u/unicode [idx] -> unicode character
    def uidx(i):
        x = us[i]; assert type(x) is ustr
        y = u_[i]; assert type(y) is unicode
        assert x == y
        return x
    for i, x in enumerate(['м','и','р','у',' ','м','и','р']):
        assert uidx(i) == x

    # b/bytes [idx]   -> bytechar of byte value @ position idx
    def bidx(i):
        x = bs[i];  assert type(x) is bstr;  assert len(x) == 1
        y = b_[i]
        if six.PY3:
            y = bytes([y])  # on py3 bytes[i] returns int instead of 1-byte string
        assert type(y) is bytes;  assert len(y) == 1
        assert x == y
        return x
    for i, x in enumerate([0xd0,0xbc,0xd0,0xb8,0xd1,0x80,0xd1,0x83,0x20,0xd0,0xbc,0xd0,0xb8,0xd1,0x80]):
        assert bidx(i) == bytearray([x])

    # u/unicode [:] -> unicode string
    class USlice:
        def __getitem__(self, key):
            x = us[key]; assert type(x) is ustr
            y = u_[key]; assert type(y) is unicode
            assert x == y
            return x
        def __len__(self): # py2
            x = len(us)
            y = len(u_)
            assert x == y
            return x
    _ = USlice()
    assert _[:]     == u"миру мир"
    assert _[1:]    ==  u"иру мир"
    assert _[:-1]   == u"миру ми"
    assert _[2:5]   ==   u"ру "
    assert _[1:-1:2]== u"иум"

    # b/bytes [:] -> bytestring
    class BSlice:
        def __getitem__(self, key):
            x = bs[key]; assert type(x) is bstr
            y = b_[key]; assert type(y) is bytes
            assert x == y
            return x
        def __len__(self): # py2
            x = len(bs)
            y = len(b_)
            assert x == y
            return x
    _ = BSlice()
    assert _[:]     == "миру мир"
    assert _[1:]    ==     b'\xbc\xd0\xb8\xd1\x80\xd1\x83 \xd0\xbc\xd0\xb8\xd1\x80'
    assert _[:-1]   == b'\xd0\xbc\xd0\xb8\xd1\x80\xd1\x83 \xd0\xbc\xd0\xb8\xd1'
    assert _[3:12]  ==             b'\xb8\xd1\x80\xd1\x83 \xd0\xbc\xd0'
    assert _[1:-1:2]== b'\xbc\xb8\x80\x83\xd0\xd0\xd1'

    # u/unicode:  index/rindex/find/rfind  return character-position
    #             methods that accept start/stop also treat them as character position
    #
    # b/bytes:    index/rindex/find/rfind  return byte-position
    #             methods that accept start/stop also treat them as byte-position
    #
    # b/u:        methods does not automatically coerce buffers to strings
    class CheckOp:
        def __init__(self, xs, x_, str2std):
            self.xs = xs
            self.x_ = x_
            self.str2std = str2std
        def __getattr__(self, meth):
            def _(*argv):
                argv_ = deepReplaceStr(argv, self.str2std)
                x = xcall(self.xs, meth, *argv)
                y = xcall(self.x_, meth, *argv_)
                assert type(x) is type(y)
                if isinstance(x, Exception):
                    assert str(x) == str(y) # ValueError('x') == ValueError('x')  is false
                else:
                    assert x == y

                # also test xs.meth(unicode|bytes|bytearray | bstr|ustr)
                for zt in [xunicode, xbytes, xbytearray, b, u]:
                    argv_z = deepReplaceStr(argv, zt)
                    z = xcall(self.xs, meth, *argv_z)
                    assert type(z) is type(x)
                    if isinstance(x, Exception):
                        assert str(z) == str(x)
                    else:
                        assert z == x

                # buffers should not be accepted
                for tbuf in buftypes:
                    have_m = [False]
                    def _(s):
                        have_m[0] = True
                        return tbuf(xbytes(s))
                    argv_m = deepReplaceStr(argv, _)
                    if have_m[0]:
                        with raises(TypeError):
                            getattr(self.xs, meth)(*argv_m)

                return x
            return _
    U = CheckOp(us, u_, xunicode)
    B = CheckOp(bs, b_, xbytes)

    assert U.count("α")             == 0
    assert B.count("α")             == 0
    assert U.count("и")             == 2
    assert B.count("и")             == 2
    assert U.count("ир")            == 2
    assert B.count("ир")            == 2
    assert U.count("ир", 2)         == 1
    assert B.count("ир", 2)         == 2
    assert U.count("ир", 2, 7)      == 0
    assert B.count("ир", 2, 7)      == 1

    assert U.find("α")              == -1
    assert B.find("α")              == -1
    assert U.find("ир")             == 1
    assert B.find("ир")             == 2
    assert U.find("ир", 2)          == 6
    assert B.find("ир", 2)          == 2
    assert U.find("ир", 2, 7)       == -1
    assert B.find("ир", 2, 7)       == 2

    assert U.rfind("α")             == -1
    assert B.rfind("α")             == -1
    assert U.rfind("ир")            == 6
    assert B.rfind("ир")            == 11
    assert U.rfind("ир", 2)         == 6
    assert B.rfind("ир", 2)         == 11
    assert U.rfind("ир", 2, 7)      == -1
    assert B.rfind("ир", 2, 7)      == 2

    _ =    U.index("α");            assert isinstance(_, ValueError)
    _ =    B.index("α");            assert isinstance(_, ValueError)
    assert U.index("ир")            == 1
    assert B.index("ир")            == 2
    assert U.index("ир", 2)         == 6
    assert B.index("ир", 2)         == 2
    _ =    U.index("ир", 2, 7);     assert isinstance(_, ValueError)
    assert B.index("ир", 2, 7)      == 2

    _ =    U.rindex("α");           assert isinstance(_, ValueError)
    _ =    B.rindex("α");           assert isinstance(_, ValueError)
    assert U.rindex("ир")           == 6
    assert B.rindex("ир")           == 11
    assert U.rindex("ир", 2)        == 6
    assert B.rindex("ир", 2)        == 11
    _ =    U.rindex("ир", 2, 7);    assert isinstance(_, ValueError)
    assert B.rindex("ир", 2, 7)     == 2

    assert U.startswith("α")        == False
    assert B.startswith("α")        == False
    assert U.startswith("мир")      == True
    assert B.startswith("мир")      == True
    assert U.startswith("мир", 5)   == True
    assert B.startswith("мир", 5)   == False
    assert U.startswith("мир", 5, 7)== False
    assert B.startswith("мир", 5, 7)== False
    assert U.startswith(())         == False
    assert B.startswith(())         == False
    assert U.startswith(("α",))     == False
    assert B.startswith(("α",))     == False
    assert U.startswith(("α","β"))  == False
    assert B.startswith(("α","β"))  == False
    assert U.startswith(("α","β","ир"))  == False
    assert B.startswith(("α","β","ир"))  == False
    assert U.startswith(("α","β","мир")) == True
    assert B.startswith(("α","β","мир")) == True

    assert U.endswith("α")          == False
    assert B.endswith("α")          == False
    assert U.endswith("мир")        == True
    assert B.endswith("мир")        == True
    assert U.endswith("мир", 2)     == True
    assert B.endswith("мир", 2)     == True
    assert U.endswith("мир", 2, 7)  == False
    assert B.endswith("мир", 2, 7)  == False
    assert U.endswith("мир", None, 3) == True
    assert B.endswith("мир", None, 3) == False
    assert U.endswith("мир", None, 6) == False
    assert B.endswith("мир", None, 6) == True
    assert U.endswith(())           == False
    assert B.endswith(())           == False
    assert U.endswith(("α",))       == False
    assert B.endswith(("α",))       == False
    assert U.endswith(("α","β"))    == False
    assert B.endswith(("α","β"))    == False
    assert U.endswith(("α","β","ир"))  == True
    assert B.endswith(("α","β","ир"))  == True
    assert U.endswith(("α","β","мир")) == True
    assert B.endswith(("α","β","мир")) == True

def test_strings_index2():
    # test_strings_index verifies __getitem__ thoroughly, but on py2
    # for [x:y] access plain python uses __getslice__ if present, while
    # pytest, because it does AST rewriting, calls __getitem__. This
    # way [x:y] handling remains untested if verified only via pytest.
    # -> test it also via running external program via plain python.
    outok = readfile(dir_testprog + "/golang_test_str_index2.txt")
    retcode, stdout, stderr = _pyrun(["golang_test_str_index2.py"],
                                cwd=dir_testprog, stdout=PIPE, stderr=PIPE)
    assert retcode == 0, (stdout, stderr)
    assert stderr == b""
    assertDoc(outok, stdout)


# verify strings iteration.
def test_strings_iter():
    # iter(u/unicode) + uiter(*) -> iterate unicode characters
    # iter(b/bytes)   + biter(*) -> iterate byte    characters
    us = u("миру мир"); u_ = u"миру мир"
    bs = b("миру мир"); b_ = xbytes("миру мир"); a_ = xbytearray(b_)

    # XIter verifies that going through all given iterators produces the same type and results.
    missing=object()
    class XIter:
        def __init__(self, typok, *viter):
            self.typok = typok
            self.viter = viter
        def __iter__(self):
            return self
        def __next__(self):
            vnext = []
            for it in self.viter:
                obj = next(it, missing)
                vnext.append(obj)
            if missing in vnext:
                assert vnext == [missing]*len(self.viter)
                raise StopIteration
            for obj in vnext:
                assert type(obj) is self.typok
                assert obj == vnext[0]
            return vnext[0]
        next = __next__ # py2

    assert list(XIter(ustr, iter(us), uiter(us), uiter(u_), uiter(bs), uiter(b_), uiter(a_))) == \
                ['м','и','р','у',' ','м','и','р']
    assert list(XIter(bstr, iter(bs), biter(us), biter(u_), biter(bs), biter(b_), biter(a_))) == \
                [b'\xd0',b'\xbc',b'\xd0',b'\xb8',b'\xd1',b'\x80',b'\xd1',b'\x83',b' ',
                 b'\xd0',b'\xbc',b'\xd0',b'\xb8',b'\xd1',b'\x80']


# verify .encode/.decode .
def test_strings_encodedecode():
    us = u('мир')
    bs = b('май')

    # encode does obj.encode and makes sure result type is bytes
    def encode(obj, *argv):
        _ = obj.encode(*argv)
        assert type(_) is bytes
        return _

    # decode does obj.decode and makes sure result type is ustr
    def decode(obj, *argv):
        _ = obj.decode(*argv)
        assert type(_) is ustr
        return _

    _ = encode(us);           assert _ == xbytes('мир')
    _ = encode(us, 'utf-8');  assert _ == xbytes('мир')
    _ = encode(bs);           assert _ == xbytes('май')
    _ = encode(bs, 'utf-8');  assert _ == xbytes('май')

    _ = decode(us);           assert _udata(_) == u'мир'
    _ = decode(us, 'utf-8');  assert _udata(_) == u'мир'
    _ = decode(bs);           assert _udata(_) == u'май'
    _ = decode(bs, 'utf-8');  assert _udata(_) == u'май'

    # !utf-8
    k8mir = u'мир'.encode('koi8-r');  assert k8mir == b'\xcd\xc9\xd2'
    b_k8mir = b(k8mir);  assert type(b_k8mir) is bstr;  assert _bdata(b_k8mir) == b'\xcd\xc9\xd2'
    u_k8mir = u(k8mir);  assert type(u_k8mir) is ustr;  assert _udata(u_k8mir) == u'\udccd\udcc9\udcd2'

    _ = decode(b_k8mir, 'koi8-r');  assert _udata(_) == u'мир'
    _ = decode(u_k8mir, 'koi8-r');  assert _udata(_) == u'мир'

    _ = encode(us, 'cp1251');  assert _ == u'мир'.encode('cp1251');  assert _ == b'\xec\xe8\xf0'
    _ = encode(bs, 'cp1251');  assert _ == u'май'.encode('cp1251');  assert _ == b'\xec\xe0\xe9'

    # decode/encode errors
    _ = decode(b_k8mir);  assert _ == u_k8mir           # no decode error with default parameters
    _ = decode(b_k8mir, 'utf-8', 'surrogateescape')     # or with explicit utf-8/surrogateescape
    assert _ == u_k8mir
    _ = decode(u_k8mir);  assert _ == u_k8mir
    _ = decode(u_k8mir, 'utf-8', 'surrogateescape');  assert _ == u_k8mir

    with raises(UnicodeDecodeError):  b_k8mir.decode('utf-8')   # decode error on unmatching explicit encoding
    with raises(UnicodeDecodeError):  u_k8mir.decode('utf-8')
    with raises(UnicodeDecodeError):  b_k8mir.decode('utf-8', 'strict')
    with raises(UnicodeDecodeError):  u_k8mir.decode('utf-8', 'strict')
    with raises(UnicodeDecodeError):  b_k8mir.decode('ascii')
    with raises(UnicodeDecodeError):  u_k8mir.decode('ascii')

    with raises(UnicodeEncodeError):  us.encode('ascii')    # encode error if target encoding cannot represent string
    with raises(UnicodeEncodeError):  bs.encode('ascii')

    _ = encode(u_k8mir);  assert _ == k8mir             # no encode error with default parameters
    _ = encode(u_k8mir, 'utf-8', 'surrogateescape')     # or with explicit utf-8/surrogateescape
    assert _ == k8mir
    _ = encode(b_k8mir);  assert _ == k8mir             # bstr.encode = bstr -> ustr -> encode
    _ = encode(b_k8mir, 'utf-8', 'surrogateescape')
    assert _ == k8mir

    # on py2 unicode.encode accepts surrogate pairs and does not complain
    # TODO(?) manually implement encode/py2 and reject surrogate pairs by default
    if six.PY3:
        with raises(UnicodeEncodeError):  # encode error if encoding is explicit specified
            u_k8mir.encode('utf-8')
        with raises(UnicodeEncodeError):
            u_k8mir.encode('utf-8', 'strict')
    with raises(UnicodeEncodeError):
        u_k8mir.encode('ascii')

    # on py2 there are encodings for which bytes.decode returns bytes
    # e.g. bytes.decode('string-escape') is actually used by pickle
    # verify that this exact semantic is preserved
    if six.PY3:
        with raises(LookupError):  bs.decode('hex')
        with raises(LookupError):  us.decode('hex')
        with raises(LookupError):  bs.decode('string-escape')
        with raises(LookupError):  us.decode('string-escape')
    else:
        _ = bs.decode('string-escape');          assert type(_) is bstr;  assert _ == bs
        _ = us.decode('string-escape');          assert type(_) is bstr;  assert _ == us
        _ = b(r'x\'y').decode('string-escape');  assert type(_) is bstr;  assert _bdata(_) == b"x'y"
        _ = u(r'x\'y').decode('string-escape');  assert type(_) is bstr;  assert _bdata(_) == b"x'y"
        _ = b('616263').decode('hex');           assert type(_) is bstr;  assert _bdata(_) == b"abc"
        _ = u('616263').decode('hex');           assert type(_) is bstr;  assert _bdata(_) == b"abc"

    # similarly for bytes.encode
    if six.PY3:
        with raises(LookupError):  bs.encode('hex')
        with raises(LookupError):  us.encode('hex')
        with raises(LookupError):  bs.encode('string-escape')
        with raises(LookupError):  us.encode('string-escape')
    else:
        _ = encode(bs, 'hex');            assert _ == b'd0bcd0b0d0b9'
        _ = encode(us, 'hex');            assert _ == b'd0bcd0b8d180'
        _ = encode(bs, 'string-escape');  assert _ == br'\xd0\xbc\xd0\xb0\xd0\xb9'
        _ = encode(us, 'string-escape');  assert _ == br'\xd0\xbc\xd0\xb8\xd1\x80'


# verify string operations like `x * 3` for all cases from bytes, bytearray, unicode, bstr and ustr.
@mark.parametrize('tx', (bytes, unicode, bytearray, bstr, ustr))
def test_strings_ops1(tx):
    x = xstr(u'мир', tx)
    assert type(x) is tx

    # *
    _ = x * 3
    assert type(_)   is tx
    assert xudata(_) == u'мирмирмир'

    _ = 3 * x
    assert type(_)   is tx
    assert xudata(_) == u'мирмирмир'


    # *=
    _ = x
    _ *= 3
    assert type(_)   is tx
    assert xudata(_) == u'мирмирмир'

    assert _ is x      if tx is bytearray  else \
           _ is not x


# verify string operations like `x + y` for all combinations of pairs from
# bytes, unicode, bstr, ustr and bytearray. Except if both x and y are std
# python types, e.g. (bytes, unicode), because those combinations are handled
# only by builtin python code and might be rejected.
@mark.parametrize('tx', (bytes, unicode, bstr, ustr, bytearray))
@mark.parametrize('ty', (bytes, unicode, bstr, ustr, bytearray))
def test_strings_ops2(tx, ty):
    # skip e.g. regular bytes vs regular unicode
    tstd = {bytes, unicode, bytearray}
    if tx in tstd  and  ty in tstd  and  tx is not ty:
        skip()

    # == != <= >= < >   for ~equal
    x = xstr(u'мир', tx);  assert type(x) is tx
    y = xstr(u'мир', ty);  assert type(y) is ty
    assert      x == y
    assert      y == x
    assert not (x != y)
    assert not (y != x)
    assert      x >= y
    assert      y >= x
    assert      x <= y
    assert      y <= x
    assert not (x > y)
    assert not (y > x)
    assert not (x < y)
    assert not (y < x)

    # now not equal
    x = xstr(u'hello ', tx)
    y = xstr(u'мир',    ty)

    # == != <= >= < >
    assert not (x == y)
    assert not (y == x)
    assert      x != y
    assert      y != x
    assert not (x >= y)
    assert      y >= x
    assert      x <= y
    assert not (y <= x)
    assert      x < y
    assert not (y < x)
    assert not (x > y)
    assert      y > x

    # +
    #
    # type(x + y) is determined by type(x):
    #   u()   +     *     ->  u()
    #   b()   +     *     ->  b()
    #   u''   +  u()/b()  ->  u()
    #   u''   +  u''      ->  u''
    #   b''   +  u()/b()  ->  b()
    #   b''   +      b''  ->  b''
    #   barr  +  u()/b()  ->  barr
    if tx in (bstr, ustr):
        tadd = tx
    elif tx in (unicode, bytes):
        if ty in (unicode, bytes, bytearray):
            tadd = tx  # we are skipping e.g. bytes + unicode
        else:
            assert ty in (bstr, ustr)
            tadd = tbu(tx)
    else:
        assert tx is bytearray
        tadd = tx

    _ = x + y
    assert type(_) is tadd
    assert _ is not x;  assert _ is not y
    assert _ == xstr(u'hello мир', tadd)

    # +=  (same typing rules as for +)
    _ = x
    _ += y
    assert type(_) is tadd
    assert _ == xstr(u'hello мир', tadd)
    assert _ is x      if tx is bytearray else \
           _ is not x


    # x % y  (not tuple at right)
    # ideally same typing rules as for +, but for `x=u'' y=b()` and `x=b'' y=u()`
    # we can't make python call y.__rmod__ .
    # see https://bugs.python.org/issue28598 for references where python implements this.
    #
    # NOTE python 3.11 reworked % handling to be generic - there we could
    # probably make y.__rmod__ to be called via tweaking __subclasscheck__
    # https://github.com/python/cpython/commit/ec382fac0db6
    if tx in (bstr, ustr):
        tmod = tx
    elif tx in (unicode, bytes):
        if ty in (unicode, bytes, bytearray):
            tmod = tx
        else:
            assert ty in (bstr, ustr)
            # on py2 str % (unicode|ustr)  gives unicode
            if six.PY2 and ty is ustr:
                if tx is bytes:
                    tmod = unicode
                else:
                    assert tx is unicode
                    tmod = ustr  # ustr is subclass of unicode -> __rmod__ is called
            else:
                tmod = tx       if  tbu(tx) is not ty  else \
                       tbu(tx)
    else:
        assert tx is bytearray
        tmod = tx

    x = xstr(u'hello %s', tx)
    if six.PY2  and  tx is bytearray: # bytearray/py2 does not support %
        _ = xbytearray(bytes(x) % y)
    else:
        _ = x % y
    assert type(_) is tmod
    assert _ == xstr(u'hello мир', tmod)
    assert _ is not x

    # x %= y  (not tuple at right;  same as in corresponding %)
    _ = x
    if six.PY2  and  tx is bytearray: # bytearray/py2 does not support %=
        _ = xbytearray(bytes(x) % y)
    else:
        _ %= y
    assert type(_) is tmod
    assert _ == xstr(u'hello мир', tmod)
    assert _ is not x   # even bytearray('%s') %= y  creates new object

    # x % (y,)
    # py3: result type is type(x) because y.__rmod__ is never called
    # py2: similar, but b'' % u'' gives u
    if six.PY2  and  tx is bytearray: # bytearray/py2 does not support %
        _ = xbytearray(bytes(x) % (y,))
    else:
        _ = x % (y,)
    ttmod = tx
    if six.PY2:
        if tx in (bytes, unicode):
            if tx is unicode or ty in (unicode, ustr):
                ttmod = unicode
            else:
                ttmod = bytes
    assert type(_) is ttmod
    assert _ == xstr(u'hello мир', ttmod)
    assert _ is not x

    # x %= (y,)
    _ = x
    if six.PY2  and  tx is bytearray: # bytearray/py2 does not support %=
        _ = xbytearray(bytes(x) % (y,))
    else:
        _ %= (y,)
    assert type(_) is ttmod
    assert _ == xstr(u'hello мир', ttmod)
    assert _ is not x   # even bytearray('%s') %= y  creates new object


# verify string operations like `x + y` for x being bstr/ustr and y being a
# type unsupported for coercion.
#
# NOTE string methods, like .join and .startswith, are verified to reject
# buffers in test_strings_methods and test_strings_index.
@mark.parametrize('tx', (bstr, ustr))
@mark.parametrize('ty', buftypes)
def test_strings_ops2_bufreject(tx, ty):
    x = xstr(u'мир', tx)
    y = ty(b'123')

    with raises(TypeError):     x + y
    with raises(TypeError):     x * y
    with raises(TypeError):     y in x

    assert  (x == y) is False           # see test_strings_ops2_eq_any
    assert  (x != y) is True
    if six.PY3:
        with raises(TypeError): "abc" >= y  # x.__op__(y) and y.__op'__(x) both return
        with raises(TypeError):     x >= y  # NotImplemented which leads py3 to raise TypeError
        with raises(TypeError):     x <= y
        with raises(TypeError):     x >  y
        with raises(TypeError):     x <  y
    else:
        "abc" >= y  # does not raise but undefined
        x >= y      # ----//----
        x <= y
        x >  y
        x <  y

    # reverse operations, e.g. memoryview + bstr
    with raises(TypeError):     y + x
    with raises(TypeError):     y * x

    # `x in y` does not raise: y is considered to be generic sequence without
    # __contains__, and so python transforms `x in y` into `x in list(y)`.
    #with raises(TypeError):     x in y

    # `y > x` does not raise when x is bstr (= provides buffer):
    y == x  # not raises TypeError  -  see test_strings_ops2_eq_any
    y != x  #
    if tx is not bstr:
        if six.PY3:
            with raises(TypeError):     y >= "abc"  # see ^^^
            with raises(TypeError):     y >= x
            with raises(TypeError):     y <= x
            with raises(TypeError):     y >  x
            with raises(TypeError):     y <  x
        else:
            y >= "abc"
            y >= x
            y <= x
            y >  x
            y <  x


# verify string operations like `x + y` for x being str/bstr/ustr and y being
# arbitrary type that defines __rop__.
@mark.parametrize('tx', (str, bstr, ustr))
def test_strings_ops2_rop_any(tx):
    # ROp(rop, x, y) represents call to y.__rop__(x)
    class ROp:
        def __init__(r, rop, x, y):
            r.rop, r.x, r.y = rop, x, y
        def __repr__(r):
            return 'ROp(%r, %r, %r)' % (r.rop, r.x, r.y)
        def __eq__(a, b):
            return isinstance(b, ROp)  and  a.rop == b.rop  and  a.x is b.x  and  a.y is b.y
        def __ne__(a, b):
            return not (a == b)

    class C:
        def __radd__(b, a):         return ROp('radd', a, b)
        def __rsub__(b, a):         return ROp('rsub', a, b)
        def __rmul__(b, a):         return ROp('rmul', a, b)
        def __rdiv__(b, a):         return ROp('rdiv', a, b)
        def __rtruediv__(b, a):     return ROp('rtruediv', a, b)
        def __rfloordiv__(b, a):    return ROp('rfloordiv', a, b)
        def __rmod__(b, a):         return ROp('rmod', a, b)
        def __rdivmod__(b, a):      return ROp('rdivmod', a, b)
        def __rpow__(b, a):         return ROp('rpow', a, b)
        def __rlshift__(b, a):      return ROp('rlshift', a, b)
        def __rrshift__(b, a):      return ROp('rrshift', a, b)
        def __rand__(b, a):         return ROp('rand', a, b)
        def __rxor__(b, a):         return ROp('rxor', a, b)
        def __ror__(b, a):          return ROp('ror', a, b)


    x = xstr(u'мир', tx)
    y = C()
    R = lambda rop: ROp(rop, x, y)

    assert x + y        == R('radd')
    assert x - y        == R('rsub')
    assert x * y        == R('rmul')
    assert x / y        == R(x32('rtruediv', 'rdiv'))
    assert x // y       == R('rfloordiv')
    # x % y is always handled by str and verified in test_strings_mod_and_format
    assert divmod(x,y)  == R('rdivmod')
    assert x ** y       == R('rpow')
    assert x << y       == R('rlshift')
    assert x >> y       == R('rrshift')
    assert x & y        == R('rand')
    assert x ^ y        == R('rxor')
    assert x | y        == R('ror')


# verify string operations like `x == *` for x being bstr/ustr.
# Those operations must succeed for any hashable type or else bstr/ustr could
# not be used as dict keys.
@mark.parametrize('tx', (bstr, ustr))
def test_strings_ops2_eq_any(tx):
    x = xstr(u'мир', tx)
    while 1:
        hx = hash(x)
        if hash(hx) == hx:  # positive int32 will have this property
            break
        x += xstr('!', tx)

    # assertNE asserts that (x==y) is False and (x!=y) is True.
    # it also asserts that e.g. x < y raises TypeError
    def assertNE(y):
        assert (x == y) is False
        assert (x != y) is True
        if six.PY3:
            with raises(TypeError): "abc" >= y  # py3: NotImplemented -> raise
            with raises(TypeError): x >= y
            with raises(TypeError): x <= y
            with raises(TypeError): x >  y
            with raises(TypeError): x <  y
        else:
            "abc" >= y  # py2: no raise on NotImplemented; result is undefined
            x >= y
            x <= y
            x >  y
            x <  y

    _ = assertNE

    _(None)
    _(0)
    _(1)
    _(2)

    assert hash(x)  == hx
    assert hash(hx) == hx
    _(hx)
    d = {x: 1, hx: 2}    # creating dict will fail if `x == hx` raises TypeError
    assert d[x]  == 1
    assert d[hx] == 2

    _(())
    _((1,))
    _((x,))

    # == wrt non-hashable type also succeeds following std python where e.g. 's' == [1] gives False
    l = [1]
    with raises(TypeError): hash(l)
    _(l)

    # also verify that internally x.__op__(y of non-string-type) returns
    # NotImplemented - exactly the same way as builtin str type does. Even
    # though `x op y` gives proper answer internally python counts on x.__op__(y)
    # to return NotImplemented so that arbitrary three-way comparison works properly.
    s = xstr(u'мир', str)
    for op in ('eq', 'ne', 'lt', 'gt', 'le', 'ge'):
        sop = getattr(s, '__%s__' % op)
        xop = getattr(x, '__%s__' % op)
        assert sop(None) is NotImplemented
        assert xop(None) is NotImplemented
        assert sop(0)    is NotImplemented
        assert xop(0)    is NotImplemented
        assert sop(hx)   is NotImplemented
        assert xop(hx)   is NotImplemented


# verify logic in `bstr % ...` and `bstr.format(...)` .
def test_strings_mod_and_format():
    # verify_fmt_all_types verifies f(fmt, args) for all combinations of
    #
    # · fmt  being             unicode, bstr, ustr
    # · args being/containing  unicode, bytes, bytearray,  bstr, ustr
    #
    # it checks that all results are the same for the case when both fmt and
    # args contain only standard unicode.
    def verify_fmt_all_types(f, fmt, args, *okv, **kw):
        excok = kw.pop('excok', False)
        assert not kw
        rok = None
        #print()
        def xfmt(fmt, args):
            exc = False
            try:
                r = f(fmt, args)    # e.g. fmt % args
            except Exception as e:
                if not excok:
                    raise
                exc = True
                r = repr(e) # because e.g. ValueError('x') == ValueError('x') is false
            #print(repr(fmt), "%", repr(args), "->", repr(r))
            if not exc:
                assert type(r) is type(fmt)
            if len(okv) != 0:
                for ok in okv:
                    if isinstance(ok, Exception):
                        ok = repr(ok)
                    else:
                        ok = xunicode(ok)
                    if r == ok:
                        break
                else:
                    raise AssertionError("result (%r) not in any of %r" % (r, okv))
            elif rok is not None:
                assert r == rok
            return r

        fmt_ustd  = deepReplaceStr(fmt, xunicode)
        fmt_u     = deepReplaceStr(fmt, u)
        fmt_b     = deepReplaceStr(fmt, b)
        args_ustd = deepReplaceStr(args, xunicode)
        args_bstd = deepReplaceStr(args, xbytes)
        args_barr = deepReplaceStr2Bytearray(args)
        args_u    = deepReplaceStr(args, u)
        args_b    = deepReplaceStr(args, b)

        # see if args_ustd could be used for stringification.
        # e.g. on py2 both str() and unicode() on UserString(u'β') raises
        # "UnicodeEncodeError: 'ascii' codec can't encode characters ..."
        args_ustd_ok = True
        if six.PY2:
            try:
                unicode(args_ustd)          # e.g. UserString
                try:
                    it = iter(args_ustd)    # e.g. (UserString,)
                    # on py2 UserDict is not really iterable - iter succeeds but
                    # going through it raises KeyError because of
                    # https://github.com/python/cpython/blob/2.7-0-g8d21aa21f2c/Lib/UserDict.py#L112-L114
                    # -> work it around
                    if six.PY2 and not hasattr(args_ustd, '__iter__'):
                        raise TypeError
                except TypeError:
                    pass
                else:
                    for _ in it:
                        unicode(_)
            except UnicodeEncodeError:
                args_ustd_ok = False

        # initialize rok from u'' % u''.
        # Skip errors on py2 because e.g. `u'α %s' % [u'β']` gives u"α [u'\\u03b2']",
        # not u"α ['β']". This way we cannot use u'' % u'' as a reference.
        # We cannot use b'' % b'' as a reference neither because e.g.
        # `'α %s' % ['β']` gives "α ['\\xce\\xb2']", not "α ['β']"
        if args_ustd_ok:
            good4rok = True
            try:
                _ = xfmt(fmt_ustd, args_ustd)   # u'' % (u'', ...)
            except AssertionError as e:
                if six.PY2  and  len(e.args) == 1  and  "not in any of" in e.args[0]:
                    good4rok = False
                else:
                    raise
            if good4rok:
                rok = _

        # if rok computation was skipped we insist on being explicitly called with ok=...
        assert (rok is not None)  or  (len(okv) != 0)

        if args_ustd_ok:
            xfmt(fmt_b, args_ustd)      # b() % (u'', ...)
            xfmt(fmt_u, args_ustd)      # u() % (u'', ...)
        xfmt(fmt_b, args_bstd)          # b() % (b'', ...)
        xfmt(fmt_u, args_bstd)          # u() % (b'', ...)
        xfmt(fmt_b, args_barr)          # b() % (bytearray, ...)
        xfmt(fmt_u, args_barr)          # u() % (bytearray, ...)
        xfmt(fmt_b, args_b)             # b() % (b(), ...)
        xfmt(fmt_u, args_b)             # b() % (b(), ...)
        xfmt(fmt_b, args_u)             # b() % (u(), ...)
        xfmt(fmt_u, args_u)             # b() % (u(), ...)
        # NOTE we don't check e.g. `u'' % u()` and `u'' % b()` because for e.g.
        # `u'α %s' % [u('β')]` the output is u"α [u("β")]" - not u"α ['β']".


    # _bprintf parses %-format ourselves. Verify that parsing first
    # NOTE here all strings are plain ASCII.
    def _(fmt, args, ok):
        fmt = '*str '+fmt
        if isinstance(ok, Exception):
            excok = True
        else:
            ok  = '*str '+ok
            excok = False
        verify_fmt_all_types(lambda fmt, args: fmt % args, fmt, args, ok, excok=excok)
        # also automatically verify "incomplete format" parsing via fmt[:l<len]
        # this works effectively only when run under std python though.
        for l in range(len(fmt)-1, -1, -1):
            verify_fmt_all_types(lambda fmt, args: fmt % args, fmt[:l], args, excok=True)

    _('%(name)s',   {'name': 123}   ,   '123')
    _('%x',         123             ,   '7b')           # flags
    _('%#x',        123             ,   '0x7b')
    _('%05d',       123             ,   '00123')
    _('%-5d',       123             ,   '123  ')
    _('% d',        123             ,   ' 123')
    _('% d',       -123             ,   '-123')
    _('%+d',        123             ,   '+123')
    _('%+d',       -123             ,   '-123')
    _('%5d',        123             ,   '  123')        # width
    _('%*d',        (5,123)         ,   '  123')
    _('%f',         1.234           ,   '1.234000')     # .prec
    _('%.f',        1.234           ,   '1')
    _('%.1f',       1.234           ,   '1.2')
    _('%.2f',       1.234           ,   '1.23')
    _('%*f',        (2,1.234)       ,   '1.234000')
    _('%.*f',       (2,1.234)       ,   '1.23')
    _('%hi',        123             ,   '123')          # len
    _('%li',        123             ,   '123')
    _('%Li',        123             ,   '123')
    _('%%',         ()              ,   '%')            # %%
    _('%10.4f',     1.234           ,   '    1.2340')   # multiple features
    _('%(x)10.4f',  {'y':0, 'x':1.234}, '    1.2340')
    _('%*.*f',      (10,4,1.234)    ,   '    1.2340')

    _('',           {}      ,   '')                     # errors
    _('',           []      ,   '')
    _('',           123     ,   TypeError('not all arguments converted during string formatting'))
    _('',           '123'   ,   TypeError('not all arguments converted during string formatting'))
    _('%s',         ()      ,   TypeError('not enough arguments for format string'))
    _('%s %s',      123     ,   TypeError('not enough arguments for format string'))
    _('%s %s',      (123,)  ,   TypeError('not enough arguments for format string'))

    _('%(x)s',      123     ,   TypeError('format requires a mapping'))
    _('%(x)s',      (123,)  ,   TypeError('format requires a mapping'))
    _('%s %(x)s',   (123,4) ,   TypeError('format requires a mapping'))
    _('%(x)s %s',   (123,4) ,   TypeError('format requires a mapping'))

    _('%(x)s %s',   {'x':1} ,   TypeError('not enough arguments for format string'))    # mixing tuple/dict
    _('%s %(x)s',   {'x':1} ,   "{'x': 1} 1")

    # for `'%4%' % ()` py2 gives '   %', but we stick to more reasonable py3 semantic
    _('%4%',        ()      ,   TypeError("not enough arguments for format string"))
    _('%4%',        1       ,   ValueError("unsupported format character '%' (0x25) at index 7"))
    _('%4%',        (1,)    ,   ValueError("unsupported format character '%' (0x25) at index 7"))
    _('%(x)%',      {'x':1} ,   ValueError("unsupported format character '%' (0x25) at index 9"))


    # parse checking complete. now verify actual %- and format- formatting

    # fmt_percent_to_bracket converts %-style format to .format-style format string.
    def fmt_percent_to_bracket(fmt):
        # replace %<x> with corresponding {} style
        # be dumb and explicit in replacement to make sure there is no chance
        # we get this logic wrong
        def _(m):
            r = {
                '%s':       '{!s}',
                '%r':       '{!r}',
                '%(x)s':    '{x!s}',
                '%(y)s':    '{y!s}',
                '%(z)s':    '{z!s}',
            }
            return r[m.group()]

        fmt_ = re.sub('%[^ ]*[a-z]', _, fmt)
        assert '%' not in fmt_
        return fmt_

    # xformat calls fmt.format with *args or **args appropriately.
    def xformat(fmt, args):
        if isinstance(args, (dict, six.moves.UserDict)):
            a = fmt.format(**args)
            if not (six.PY2 and type(fmt) is unicode):
                b = fmt.format_map(args)    # py2: no unicode.format_map()
                assert a == b
            return a
        elif isinstance(args, tuple):
            return fmt.format(*args)
        else:
            return fmt.format(args) # it was e.g. `'%s' % 123`

    # _ verifies `fmt % args` and `fmt'.format(args)`
    # if fmt has no '%' only .format(args) is verified.
    def _(fmt, args, *okv):
        if '%' in fmt:
            verify_fmt_all_types(lambda fmt, args: fmt % args,
                                 fmt, args, *okv)
            # compute fmt' for .format verification
            fmt_ = fmt_percent_to_bracket(fmt)
            # and assert that .format result is the same as for %
            # compare to b() formatting because else on py2 we hit unicode % issues
            # we, anyway, just verified b() % above.
            if len(okv) == 0:
                okv = [b(fmt) % args]
        else:
            fmt_ = fmt
        verify_fmt_all_types(xformat, fmt_, args, *okv)

    # NOTE *str to force str -> bstr/ustr even for ASCII string
    _("*str a %s z",  123                         , "*str a 123 z")
    _("*str a %s z",  '*str \'"\x7f'              , "*str a *str '\"\x7f z")
    _("*str a %s z",  'β'                         , "*str a β z")
    _("*str a %s z",  ('β',)                      , "*str a β z")
    _("*str a %s z",  ['β']                       , "*str a ['β'] z")

    _("a %s π",  123                              , "a 123 π")
    _("a %s π",  '*str \'"\x7f'                   , "a *str '\"\x7f π")
    _("a %s π",  'β'                              , "a β π")
    _("a %s π",  ('β',)                           , "a β π")
    _("a %s π",  ['β']                            , "a ['β'] π")

    _("α %s z",  123                              , "α 123 z")
    _("α %s z",  '*str \'"\x7f'                   , "α *str '\"\x7f z")
    _("α %s z",  'β'                              , "α β z")
    _("α %s z",  ('β',)                           , "α β z")
    _("α %s z",  ['β']                            , "α ['β'] z")

    _("α %s π",  123                              , "α 123 π")
    _("α %s π",  '*str \'"\x7f'                   , "α *str '\"\x7f π")
    _("α %s π",  'β'                              , "α β π")
    _("α %s π",  ('β',)                           , "α β π")
    _("α %s π",  ('β',)                           , "α β π")
    _("α %s %s π",  ('β', 'γ')                    , "α β γ π")
    _("α %s %s %s π",  ('β', 'γ', 'δ')            , "α β γ δ π")
    _("α %s %s %s %s %s %s %s π",  (1, 'β', 2, 'γ', 3, 'δ', 4),
                                                    "α 1 β 2 γ 3 δ 4 π")
    _("α %s π",  []                               , "α [] π")
    _("α %s π",  ([],)                            , "α [] π")
    _("α %s π",  ((),)                            , "α () π")
    _("α %s π",  set()                            , x32("α set() π", "α set([]) π"))
    _("α %s π",  (set(),)                         , x32("α set() π", "α set([]) π"))
    _("α %s π",  frozenset()                      , x32("α frozenset() π", "α frozenset([]) π"))
    _("α %s π",  (frozenset(),)                   , x32("α frozenset() π", "α frozenset([]) π"))
    _("α %s π",  ({},)                            , "α {} π")
    _("α %s π",  ['β']                            , "α ['β'] π")
    _("α %s π",  (['β'],)                         , "α ['β'] π")
    _("α %s π",  (('β',),)                        , "α ('β',) π")
    _("α %s π",  {'β'}                            , x32("α {'β'} π", "α set(['β']) π"))
    _("α %s π",  ({'β'},)                         , x32("α {'β'} π", "α set(['β']) π"))
    _("α %s π",  frozenset({'β'})                 , x32("α frozenset({'β'}) π", "α frozenset(['β']) π"))
    _("α %s π",  (frozenset({'β'}),)              , x32("α frozenset({'β'}) π", "α frozenset(['β']) π"))
    _("α %s π",  ({'β':'γ'},)                     , "α {'β': 'γ'} π")
    _("α %s %s π",  ([1, 'β', 2], 345)            , "α [1, 'β', 2] 345 π")
    _("α %s %s π",  ((1, 'β', 2), 345)            , "α (1, 'β', 2) 345 π")
    # NOTE set/frozenset/dict: print order is "random"
    _("α %s %s π",  ({1, 'β'}, 345)               , *x32(("α {1, 'β'} 345 π",      "α {'β', 1} 345 π"),
                                                         ("α set([1, 'β']) 345 π", "α set(['β', 1]) 345 π")))
    _("α %s %s π",  (frozenset({1, 'β'}), 345)    , *x32(("α frozenset({1, 'β'}) 345 π", "α frozenset({'β', 1}) 345 π"),
                                                         ("α frozenset([1, 'β']) 345 π", "α frozenset(['β', 1]) 345 π"))),
    _("α %s %s π",  ({1:'мир', 'β':'труд'}, 345)  , *x32(("α {1: 'мир', 'β': 'труд'} 345 π",), # py3: dict is insert-order
                                                         ("α {1: 'мир', 'β': 'труд'} 345 π", "α {'β': 'труд', 1: 'мир'} 345 π")))


    # recursive list
    l = [1,]; l += [l, 'мир']
    _('α %s π', (l,)                              , "α [1, [...], 'мир'] π")

    # recursive tuple
    t = (1, []); t[1].append((t, 'мир'))
    _('α %s π', (t,)                              , "α (1, [((...), 'мир')]) π")

    # recursive set
    s = {1}; s.add(hlist([s]))
    _('α %s π', (s,)                              , x32("α {[set(...)], 1} π", "α set([[set(...)], 1]) π"))

    # recursive frozenset
    l = hlist()
    f = frozenset({1, l}); l.append(f)
    _('α %s π', (f,)                              , *x32(("α frozenset({1, [frozenset(...)]}) π", "α frozenset({[frozenset(...)], 1}) π"),
                                                         ("α frozenset([1, [frozenset(...)]]) π", "α frozenset([[frozenset(...)], 1]) π")))

    # recursive dict (via value)
    d = {1:'мир'}; d.update({2:d})
    _('α %s π', (d,)                              , *x32(("α {1: 'мир', 2: {...}} π",),
                                                         ("α {1: 'мир', 2: {...}} π", "α {2: {...}, 1: 'мир'} π")))

    # recursive dict (via key)
    l = hlist([1])
    d = {l:'мир'}; l.append(d)
    _('α %s π', (d,)                              , "α {[1, {...}]: 'мир'} π")


    # old-style class with __str__
    class Cold:
        def __repr__(self): return "Cold()"
        def __str__(self):  return u"Класс (old)"
    _('α %s π', Cold()                            , "α Класс (old) π")
    _('α %s π', (Cold(),)                         , "α Класс (old) π")

    # new-style class with __str__
    class Cnew(object):
        def __repr__(self): return "Cnew()"
        def __str__(self):  return u"Класс (new)"
    _('α %s π', Cnew()                            , "α Класс (new) π")
    _('α %s π', (Cnew(),)                         , "α Класс (new) π")


    # custom classes inheriting from set/list/tuple/dict/frozenset
    class L(list):      pass
    class T(tuple):     pass
    class S(set):       pass
    class F(frozenset): pass
    class D(dict):      pass
    _('α %s π', L(['β',3])        , "α ['β', 3] π")
    _('α %s π', (L(['β',3]),)     , "α ['β', 3] π")
    _('α %s π', (T(['β',3]),)     , "α ('β', 3) π")
    # NOTE set/frozenset/dict: print order is "random"
    _('α %s π', S(['β',3])        , *x32(("α S({'β', 3}) π", "α S({3, 'β'}) π"),
                                         ("α S(['β', 3]) π", "α S([3, 'β']) π")))
    _('α %s π', (S(['β',3]),)     , *x32(("α S({'β', 3}) π", "α S({3, 'β'}) π"),
                                         ("α S(['β', 3]) π", "α S([3, 'β']) π")))
    _('α %s π', F(['β',3])        , *x32(("α F({'β', 3}) π", "α F({3, 'β'}) π"),
                                         ("α F(['β', 3]) π", "α F([3, 'β']) π")))
    _('α %s π', (F(['β',3]),)     , *x32(("α F({'β', 3}) π", "α F({3, 'β'}) π"),
                                         ("α F(['β', 3]) π", "α F([3, 'β']) π")))
    _('α %s π', (D([('β','γ'), (3,4)]),)
                                  , *x32(("α {'β': 'γ', 3: 4} π",),
                                         ("α {'β': 'γ', 3: 4} π", "α {3: 4, 'β': 'γ'} π")))

    # well-known classes

    # namedtuple
    cc = collections; xcc = six.moves
    Point = cc.namedtuple('Point', ['x', 'y'])
    verify_fmt_all_types(lambda fmt, args: fmt % args,
      'α %s π',   Point('β','γ')              , TypeError("not all arguments converted during string formatting"), excok=True)
    _('α %s %s π',Point('β','γ')              , "α β γ π")
    _('α %s π',  (Point('β','γ'),)            , "α Point(x='β', y='γ') π")
    # deque
    _('α %s π', cc.deque(['β','γ'])           , "α deque(['β', 'γ']) π")
    _('α %s π', (cc.deque(['β','γ']),)        , "α deque(['β', 'γ']) π")
    # Counter  (inherits from dict)
    _('α %s π', (cc.Counter({'β':1}),)        , "α Counter({'β': 1}) π")
    # OrderedDict
    _('α %s π', (cc.OrderedDict([(1,'мир'), ('β','труд')]),)
                                              , "α OrderedDict([(1, 'мир'), ('β', 'труд')]) π")
    # defaultdict
    _('α %s π', (cc.defaultdict(int, {'β':1}),)
                                              , x32("α defaultdict(<class 'int'>, {'β': 1}) π",
                                                    "α defaultdict(<type 'int'>, {'β': 1}) π"))
    # UserDict
    _('α %s π', (xcc.UserDict({'β':1}),)      , "α {'β': 1} π")
    # UserList
    _('α %s π', xcc.UserList(['β','γ'])       , "α ['β', 'γ'] π")
    _('α %s π', (xcc.UserList(['β','γ']),)    , "α ['β', 'γ'] π")
    # UserString
    _('α %s π', xcc.UserString('βγ')          , "α βγ π")
    _('α %s π', (xcc.UserString('βγ'),)       , "α βγ π")


    # custom classes inheriting from bytes/unicode/bytearray
    class B(bytes): pass
    class BB(bytes):
        def __repr__(self): return "BB(байты)"
        def __str__(self):  return "байты"
    class U(unicode): pass
    class UU(unicode):
        def __repr__(self): return "UU(юникод)"
        def __str__(self):  return "юникод"
        __unicode__ = __str__
    class A(bytearray): pass
    class AA(bytearray):
        def __repr__(self): return "AA(байтмассив)"
        def __str__(self):  return "байтмассив"

    def M(fmt, args, ok):
        # verify only `b() % args`  and `u() % args` since for e.g. `u'' % b''` the result is different
        bfmt = b(fmt)
        ufmt = u(fmt)
        br   = bfmt % args  #;print(repr(bfmt), " % ", repr(args), " -> ", repr(br))
        ur   = ufmt % args  #;print(repr(ufmt), " % ", repr(args), " -> ", repr(ur))
        assert type(br) is bstr
        assert type(ur) is ustr
        assert br == ok
        assert ur == ok

        # verify b().format(args)  and  u().format(args)
        fmt_  = fmt_percent_to_bracket(fmt)
        bfmt_ = b(fmt_)
        ufmt_ = u(fmt_)
        br_   = xformat(bfmt_, args)  #;print(repr(bfmt), " .format ", repr(args), " -> ", repr(br))
        ur_   = xformat(ufmt_, args)  #;print(repr(ufmt), " .format ", repr(args), " -> ", repr(ur))
        assert type(br_) is bstr
        assert type(ur_) is ustr
        assert br_ == ok
        assert ur_ == ok

    M("α %s π",  U (      u'май')         , "α май π")
    M("α %s π", (U (      u'май'),)       , "α май π")
    M("α %s π", [U (      u'май')]        , "α ['май'] π")
    M("α %s π",  UU(      u'май2')        , "α юникод π")       # not май2
    M("α %s π", (UU(      u'май2'),)      , "α юникод π")       # not май2
    M("α %s π", [UU(      u'май2')]       , "α [UU(юникод)] π") # not [май2]

    M("α %s π",  B (xbytes('мир'))        , "α мир π")
    M("α %s π", (B (xbytes('мир')),)      , "α мир π")
    M("α %s π", [B (xbytes('мир'))]       , "α ['мир'] π")
    M("α %s π",  BB(xbytes('мир2'))       , "α байты π")        # not мир2
    # vvv does not work on py3 as b'' % b'' does not consult __str__ nor __bytes__ of the argument
    # even though it is not 100% we are ok here, because customizing bytes or unicode is very exotic
    if six.PY2:
        M("α %s π", (BB(xbytes('мир2')),)     , "α байты π")    # not мир2
    M("α %s π", [BB(xbytes('мир2'))]      , "α [BB(байты)] π")  # not [мир2]

    M("α %s π",  A (xbytes('труд'))       , "α труд π")
    M("α %s π", (A (xbytes('труд')),)     , "α труд π")
    M("α %s π", [A (xbytes('труд'))]      , "α ['труд'] π")
    M("α %s π",  AA(xbytes('труд2'))      , "α байтмассив π")       # not труд2
    M("α %s π", (AA(xbytes('труд2')),)    , "α байтмассив π")       # not труд2
    M("α %s π", [AA(xbytes('труд2'))]     , "α [AA(байтмассив)] π") # not [труд2]


    # dict at right
    # less tests because stringification of arguments is already thoroughly
    # verified with "tuple at right" tests above.
    _("*str a %(x)s z",             {'x': 123})
    _("*str a %(x)s z",             {'x': '*str \'"\x7f'})
    _("*str a %(x)s z",             {'x': 'β'})
    _("*str a %(x)s z",             {'x': ['β']}                    , "*str a ['β'] z")
    _("*str a %(x)s %(y)s z",       {'x':'β', 'y':'γ'})
    _("*str a %(x)s %(y)s %(z)s z", {'x':'β', 'y':'γ', 'z':'δ'})

    _("a %(x)s π",                  {'x': 123})
    _("a %(x)s π",                  {'x': '*str \'"\x7f'})
    _("a %(x)s π",                  {'x': 'β'})
    _("a %(x)s π",                  {'x': ['β']}                    , "a ['β'] π")
    _("a %(x)s %(y)s π",            {'x': 'β', 'y':'γ'})
    _("a %(x)s %(y)s %(z)s π",      {'x': 'β', 'y':'γ', 'z':'δ'})

    _("α %(x)s z",                  {'x': 123})
    _("α %(x)s z",                  {'x': '*str \'"\x7f'})
    _("α %(x)s z",                  {'x': 'β'})
    _("α %(x)s z",                  {'x': ['β']}                    , "α ['β'] z")
    _("α %(x)s %(y)s z",            {'x': 'β', 'y':'γ'})
    _("α %(x)s %(y)s %(z)s z",      {'x': 'β', 'y':'γ', 'z':'δ'})

    _("α %(x)s π",                  {'x': 123})
    _("α %(x)s π",                  {'x': '*str \'"\x7f'})
    _("α %(x)s π",                  {'x': 'β'})
    _("α %(x)s π",                  {'x': ['β']}                    , "α ['β'] π")
    _("α %(x)s %(y)s π",            {'x':'β', 'y':'γ'})
    _("α %(x)s %(y)s %(z)s π",      {'x':'β', 'y':'γ', 'z':'δ'})

    _("*str a %(x)s z",             xcc.UserDict({'x': 'β'}))
    _("α %(x)s π",                  xcc.UserDict({'x': 'β'}))


    # %r (and !r)
    M("α %r",   u'z'                    , x32("α 'z'",    "α u'z'"))
    M("α %r",   u'β'                    , x32("α 'β'",    "α u'β'"))
    M("α %r",   b'z'                    , x32("α b'z'",   "α 'z'"))
    M("α %r",   xbytes('β')             , x32("α b'β'",   "α 'β'"))
    M("α %r",   xbytearray('β')         , "α bytearray(b'β')")
    M("α %r",   b('β')                  , "α b('β')")
    M("α %r",   u('β')                  , "α u('β')")
    M("α %r",   [u'z']                  , x32("α ['z']",  "α [u'z']"))
    M("α %r",   [u'β']                  , x32("α ['β']",  "α [u'β']"))
    M("α %r",   [b'z']                  , x32("α [b'z']", "α ['z']"))
    M("α %r",   [xbytes('β')]           , x32("α [b'β']", "α ['β']"))
    M("α %r",   [xbytearray('β')]       , "α [bytearray(b'β')]")
    M("α %r",   [b('β')]                , "α [b('β')]")
    M("α %r",   [u('β')]                , "α [u('β')]")

    # some explicit verifications for .format()
    _("*str hello  {}",     ("world",))
    _("*str hello  {}",     (["world"],))
    _("*str hello  {}",     ("мир",))
    _("*str hello  {}",     (["мир"],)              , "*str hello  ['мир']")
    _("привет {}",          ("мир",))
    _("привет {}",          (["мир"],)              , "привет ['мир']")
    _("привет {0}, {1}",    ("Петя", "Вася"))
    _("привет {name}",      {'name': "Ваня"})
    _("привет {name}",      {"name": "Тигра"}       , "привет Тигра")
    _("привет {name!s}",    {"name": "Винни"}       , "привет Винни")
    _("привет {name:>10}",  {"name": "Пух"}         , "привет        Пух")
    _("привет {!s}",        ("мир",))
    _("привет {!s}",        (["мир"],)              , "привет ['мир']")
    _("привет {:>10}",      ("мир",))
    _("привет {:>{}} {}",   ("мир", 10, "α"))
    _("привет {:02x}",      (23,))


# verify __format__ + format() builtin
def test_strings__format__():
    assert "привет {}".format("мир") == "привет мир"
    assert "привет {}".format(b("мир")) == "привет мир"
    assert "привет {}".format(u("мир")) == "привет мир"

    assert format(u"мир")       == u"мир"
    assert format(u"мир", "")   == u"мир"
    assert format(u"мир", "s")  == u"мир"
    assert format(u"мир", ">5") == u"  мир"
    fb  = format(b("мир"))
    fb_ = format(b("мир"), "")
    fbs = format(b("мир"), "s")
    fb5 = format(b("мир"), ">5")
    assert type(fb)  is ustr # NOTE ustr, not bstr due to b.__format__ returning u
    assert type(fb_) is ustr
    assert type(fbs) is ustr
    assert type(fb5) is ustr
    assert fb  == "мир"
    assert fb_ == "мир"
    assert fbs == "мир"
    assert fb5 == "  мир"
    fu  = format(u("мир"))
    fu_ = format(u("мир"), "")
    fus = format(u("мир"), "s")
    fu5 = format(u("мир"), ">5")
    assert type(fu)  is ustr
    assert type(fu_) is ustr
    assert type(fus) is ustr
    assert type(fu5) is ustr
    assert fu  == "мир"
    assert fu_ == "мир"
    assert fus == "мир"
    assert fu5 == "  мир"

    # string.__format__ accepts only '' and 's' format codes
    for fmt_spec in "abcdefghijklmnopqrstuvwxyz":
        if fmt_spec == 's':
            continue
        with raises(ValueError): format( u"мир",  fmt_spec)
        with raises(ValueError): format(b("мир"), fmt_spec)
        with raises(ValueError): format(u("мир"), fmt_spec)


# verify print for bstr/ustr.
def test_strings_print():
    outok = readfile(dir_testprog + "/golang_test_str.txt")
    retcode, stdout, stderr = _pyrun(["golang_test_str.py"],
                                cwd=dir_testprog, stdout=PIPE, stderr=PIPE)
    assert retcode == 0, (stdout, stderr)
    assert stderr == b""
    assertDoc(outok, stdout)


# verify methods of bstr/ustr.
def test_strings_methods():
    # checkop verifies that `s.meth(*argv, **kw)` gives the same result for s,
    # argv and kw being various combinations of unicode,bstr,ustr, bytes/bytearray.
    def checkop(s, meth, *argv, **kw):
        if six.PY3:
            assert type(s) is str
        else:
            assert type(s) in (str, unicode)    # some tests use unicode because \u does not work in str literals
        ok = kw.pop('ok')
        if six.PY2:
            ok = deepReplaceStr(ok, xunicode)
        optional = kw.pop('optional', False)
        bs = b(s)
        us = u(s)
        # verify {str,bstr,ustr}.meth with str arguments
        # on py2 use unicode(s/args) because e.g. 'мир'.capitalize()
        # gives correct result only on unicode, not regular str.
        argv_unicode = deepReplaceStr(argv, xunicode)
        kw_unicode   = deepReplaceStr(kw,   xunicode)
        if six.PY3:
            r = xcall(s, meth, *argv, **kw)
        else:
            s = xunicode(s)
            r = xcall(s, meth, *argv_unicode, **kw_unicode)

        # we provide fallback implementations on e.g. py2
        if isinstance(r, NotImplementedError):
            if not optional:
                r = ok
        else:
            assert r == ok

        assert type(s) is unicode
        br = xcall(bs, meth, *argv, **kw)
        ur = xcall(us, meth, *argv, **kw)

        def assertDeepEQ(a, b, bstrtype):
            # `assert not isinstance(a, (bstr, ustr))` done carefully not to
            # break when bytes/unicode are patched with bstr/ustr
            if isinstance(a, bytes):    assert type(a) is bytes
            if isinstance(a, unicode):  assert type(a) is unicode

            if type(a) is unicode:
                assert type(b) is bstrtype
                assert a == b
                return

            assert type(b) is type(a)

            if isinstance(a, (list, tuple)):
                assert len(a) == len(b)
                for i in range(len(a)):
                    assertDeepEQ(a[i], b[i], bstrtype)
            elif isinstance(a, dict):
                assert len(a) == len(b)
                for k, v in a.items():
                    v_ = b[k]
                    assertDeepEQ(v, v_, bstrtype)
            elif isinstance(a, Exception):
                assertDeepEQ(a.args, b.args, type(''))  # NOTE bstr is not raised in exceptions
            else:
                assert a == b

        assertDeepEQ(r, br, bstr)
        assertDeepEQ(r, ur, ustr)

        # verify {bstr,ustr}.meth with arguments being b/u instead of str
        #
        # NOTE str.meth does not work with b - on py3 e.g. unicode.center
        # checks fillchar to be instance of unicode.
        argv_b = deepReplaceStr(argv, b)
        argv_u = deepReplaceStr(argv, u)
        kw_b   = deepReplaceStr(kw,   b)
        kw_u   = deepReplaceStr(kw,   u)

        br_b = xcall(bs, meth, *argv_b, **kw_b)
        br_u = xcall(bs, meth, *argv_u, **kw_u)
        ur_b = xcall(us, meth, *argv_b, **kw_b)
        ur_u = xcall(us, meth, *argv_u, **kw_u)

        assertDeepEQ(r, br_b, bstr)
        assertDeepEQ(r, br_u, bstr)
        assertDeepEQ(r, ur_b, ustr)
        assertDeepEQ(r, ur_u, ustr)

        # verify {bstr,ustr}.meth with arguments being bytes/unicode/bytearray instead of str
        argv_bytes = deepReplaceStr(argv, xbytes)
        argv_barr  = deepReplaceStr2Bytearray(argv)
        kw_bytes   = deepReplaceStr(kw,   xbytes)
        kw_barr    = deepReplaceStr2Bytearray(kw)

        br_bytes   = xcall(bs, meth, *argv_bytes,   **kw_bytes)
        br_unicode = xcall(bs, meth, *argv_unicode, **kw_unicode)
        br_barr    = xcall(bs, meth, *argv_barr,    **kw_barr)
        ur_bytes   = xcall(us, meth, *argv_bytes,   **kw_bytes)
        ur_unicode = xcall(us, meth, *argv_unicode, **kw_unicode)
        ur_barr    = xcall(us, meth, *argv_barr,    **kw_barr)

        assertDeepEQ(r, br_bytes,   bstr) # everything is converted to bstr, not bytes
        assertDeepEQ(r, br_unicode, bstr) # ----//----                       not unicode
        assertDeepEQ(r, br_barr,    bstr) # ----//----                       not bytearray
        assertDeepEQ(r, ur_bytes,   ustr) # ----//----              to ustr
        assertDeepEQ(r, ur_unicode, ustr)
        assertDeepEQ(r, ur_barr,    ustr)

        # verify that {bstr,ustr}.meth does not implicitly convert buffer to string
        if not hasattr(bs, meth):  # e.g. bstr.removeprefix on py2
            assert not hasattr(us, meth)
            return

        for tbuf in buftypes:
            _bufview = [False]
            def bufview(s):
                _bufview[0] = True
                return tbuf(xbytes(s))
            argv_buf    = deepReplaceStr(argv, bufview)
            argv_hasbuf = _bufview[0]

            _bufview[0] = False
            kw_buf      = deepReplaceStr(kw,   bufview)
            kw_hasbuf   = _bufview[0]

            if argv_hasbuf:
                with raises(TypeError):
                    getattr(bs, meth)(*argv_buf, **kw)
                with raises(TypeError):
                    getattr(us, meth)(*argv_buf, **kw)
            if kw_hasbuf:
                with raises(TypeError):
                    getattr(bs, meth)(*argv, **kw_buf)
                with raises(TypeError):
                    getattr(us, meth)(*argv, **kw_buf)


    # Verifier provides syntactic sugar for checkop: V.attr returns wrapper around checkop(V.text, attr).
    class Verifier:
        def __init__(self, text):
            self.text = text
        def __getattr__(self, meth):
            def _(*argv, **kw):
                checkop(self.text, meth, *argv, **kw)
            return _

    _ = Verifier

    _("миру мир").__contains__("ру",                ok=True)
    _("миру мир").__contains__("α",                 ok=False)
    _("мир").capitalize(                            ok="Мир")
    _("МиР").casefold(                              ok="мир",   optional=True)  # py3.3
    _("мир").center(10,                             ok="   мир    ")
    _("мир").center(10, "ж",                        ok="жжжмиржжжж")
    # count, endswith       - tested in test_strings_index
    _("миру\tмир").expandtabs(                      ok="миру    мир")
    _("миру\tмир").expandtabs(2,                    ok="миру  мир")
    # find, index           - tested in test_strings_index
    _("мир").isalnum(                               ok=True)
    _("мир!").isalnum(                              ok=False)
    _("мир").isalpha(                               ok=True)
    _("мир!").isalpha(                              ok=False)
    _("мир").isascii(                               ok=False,   optional=True)  # py3.7
    _("hello").isascii(                             ok=True,    optional=True)  # py3.7
    _("hellЫ").isascii(                             ok=False,   optional=True)  # py3.7
    _("123 мир").isdecimal(                         ok=False)
    _("123 q").isdecimal(                           ok=False)
    _("123").isdecimal(                             ok=True)
    _("мир").isdigit(                               ok=False)
    _("123 мир").isdigit(                           ok=False)
    _("123 q").isdigit(                             ok=False)
    _("123").isdigit(                               ok=True)
    _("٤").isdigit(                                 ok=True)                    # arabic 4
    _("мир").isidentifier(                          ok=True,    optional=True)  # py3.0
    _("мир$").isidentifier(                         ok=False,   optional=True)  # py3.0
    _("мир").islower(                               ok=True)
    _("Мир").islower(                               ok=False)
    _("мир").isnumeric(                             ok=False)
    _("123").isnumeric(                             ok=True)
    _("0x123").isnumeric(                           ok=False)
    _("мир").isprintable(                           ok=True,    optional=True)  # py3.0
    _(u"\u2009").isspace(                           ok=True)                    # thin space
    _("  ").isspace(                                ok=True)
    _("мир").isspace(                               ok=False)
    _("мир").istitle(                               ok=False)
    _("Мир").istitle(                               ok=True)
    _("МИр").istitle(                               ok=False)
    _(" мир ").join(["да", "май", "труд"],          ok="да мир май мир труд")
    _("мир").ljust(10,                              ok="мир       ")
    _("мир").ljust(10, 'ж',                         ok="миржжжжжжж")
    _("МиР").lower(                                 ok="мир")
    _(u"\u2009 мир").lstrip(                        ok="мир")
    _(u"\u2009 мир\u2009 ").lstrip(                 ok=u"мир\u2009 ")
    _("мммир").lstrip('ми',                         ok="р")
    _("миру мир").partition('ру',                   ok=("ми", "ру", " мир"))
    _("миру мир").partition('ж',                    ok=("миру мир", "", ""))
    _("миру мир").removeprefix("мир",               ok="у мир", optional=True)  # py3.9
    _("миру мир").removesuffix("мир",               ok="миру ", optional=True)  # py3.9
    _("миру мир").replace("ир", "ж",                ok="мжу мж")
    _("миру мир").replace("ир", "ж", 1,             ok="мжу мир")
    # rfind, rindex         - tested in test_strings_index
    _("мир").rjust(10,                              ok="       мир")
    _("мир").rjust(10, 'ж',                         ok="жжжжжжжмир")
    _("миру мир").rpartition('ру',                  ok=("ми", "ру", " мир"))
    _("миру мир").rpartition('ж',                   ok=("", "", "миру мир"))
    _("мир").rsplit(                                ok=["мир"])
    _("привет мир").rsplit(                         ok=["привет", "мир"])
    _(u"привет\u2009мир").rsplit(                   ok=["привет", "мир"])
    _("привет мир").rsplit("и",                     ok=["пр", "вет м", "р"])
    _("привет мир").rsplit("и", 1,                  ok=["привет м", "р"])
    _(u"мир \u2009").rstrip(                        ok="мир")
    _(u" мир \u2009").rstrip(                       ok=" мир")
    _("мируу").rstrip('ру',                         ok="ми")
    _("мир").split(                                 ok=["мир"])
    _("привет мир").split(                          ok=["привет", "мир"])
    _(u"привет\u2009мир").split(                    ok=['привет', 'мир'])
    _("привет мир").split("и",                      ok=["пр", "вет м", "р"])
    _("привет мир").split("и", 1,                   ok=["пр", "вет мир"])
    _("мир").splitlines(                            ok=["мир"])
    _("миру\nмир").splitlines(                      ok=["миру", "мир"])
    _("миру\nмир").splitlines(True,                 ok=["миру\n", "мир"])
    _("миру\nмир\n").splitlines(True,               ok=["миру\n", "мир\n"])
    _("мир\nтруд\nмай\n").splitlines(               ok=["мир", "труд", "май"])
    _("мир\nтруд\nмай\n").splitlines(True,          ok=["мир\n", "труд\n", "май\n"])
    # startswith            - tested in test_strings_index
    _(u"\u2009 мир \u2009").strip(                  ok="мир")
    _("миру мир").strip('мир',                      ok="у ")
    _("МиР").swapcase(                              ok="мИр")
    _("МиР").title(                                 ok="Мир")
    _("мир").translate({ord(u'м'):ord(u'и'), ord(u'и'):'я', ord(u'р'):None},        ok="ия")
    _(u"\u0000\u0001\u0002.").translate([u'м', ord(u'и'), None],                    ok="ми.")
    _("МиР").upper(                                 ok="МИР")
    _("мир").zfill(10,                              ok="0000000мир")
    _("123").zfill(10,                              ok="0000000123")


# verify bstr.translate in bytes mode
def test_strings_bstr_translate_bytemode():
    bs = b('мир')
    b_ = xbytes('мир')

    def _(*argv):
        rb  = bs.translate(*argv)
        rok = b_.translate(*argv)
        assert rb == rok

    _(None)
    _(None, b'')
    _(None, b'\xd1')
    _(None, b'\x80\xd1')

    t = bytearray(range(0x100))
    t[0x80] = 0x81
    t[0xbc] = 0xbd
    t = bytes(t)
    _(t)
    _(t, b'')
    _(None, b'\xd1')
    _(None, b'\x80\xd1')


# verify bstr/ustr maketrans
def test_strings_maketrans():
    def _(argv, ok):
        rok = xcall(unicode, 'maketrans', *argv)
        # py2 unicode does not have maketrans
        if six.PY2 and isinstance(rok, NotImplementedError):
            rok = ok
        assert rok == ok

        rb  = xcall(bstr,    'maketrans', *argv)
        ru  = xcall(ustr,    'maketrans', *argv)

        argv_b = deepReplaceStr(argv, b)
        argv_u = deepReplaceStr(argv, u)
        rb_b = xcall(bstr, 'maketrans', *argv_b)
        rb_u = xcall(bstr, 'maketrans', *argv_u)
        ru_b = xcall(ustr, 'maketrans', *argv_b)
        ru_u = xcall(ustr, 'maketrans', *argv_u)

        assert rok == rb
        assert rok == ru
        assert rok == rb_b
        assert rok == rb_u
        assert rok == ru_b
        assert rok == ru_u

    _( ({100:'ы', 200:'я'},)        , {100:u'ы',        200:u'я'} )
    _( ({'α':'ы', 'β':'я'},)        , {ord(u'α'):u'ы',  ord(u'β'):u'я'} )
    _( ('αβ', 'ыя')                 , {ord(u'α'):ord(u'ы'),  ord(u'β'):ord(u'я')} )
    _( ('αβ', 'ыя', 'πρ')           , {ord(u'α'):ord(u'ы'),  ord(u'β'):ord(u'я'),
                                       ord(u'π'):None,       ord(u'ρ'):None} )

# verify behaviour of bstr|ustr subclasses.
@mark.parametrize('tx', (unicode, bstr, ustr))
def test_strings_subclasses(tx):
    x = xstr(u'мир', tx);  assert type(x) is tx

    # subclass without __str__
    class MyStr(tx):
        pass
    xx = MyStr(x);  assert type(xx) is MyStr
    _  = tx(xx);    assert type(_)  is tx   ; assert _ == x  # e.g. unicode(MyStr) -> unicode, not MyStr
    _  = bstr(xx);  assert type(_)  is bstr ; assert _ == 'мир'
    _  = ustr(xx);  assert type(_)  is ustr ; assert _ == 'мир'
    _  = b(xx);     assert type(_)  is bstr ; assert _ == 'мир'
    _  = u(xx);     assert type(_)  is ustr ; assert _ == 'мир'

    # __str__ returns *str, not MyStr
    txstr = {
        unicode: str,
        bstr:    x32(ustr, bstr),
        ustr:    x32(ustr, bstr),
    }[tx]
    if six.PY2  and  tx is unicode: # on py2 unicode.__str__ raises UnicodeEncodeError:
        aa = u'mir'                 # `'ascii' codec can't encode ...` -> do the test on ascii
        _  = aa.__str__();  assert _ == 'mir'
    else:
        _  = xx.__str__();  assert _ == 'мир'
    assert type(_) is txstr

    # for bstr/ustr  __unicode__ returns *str, never MyStr
    #                __bytes__   returns bytes leaving string domain
    # (builtin unicode has no __unicode__/__bytes__)
    if tx is not unicode:
        _ = xx.__unicode__();  assert type(_) is ustr;  assert _ == 'мир'
        _ = xx.__bytes__();    assert type(_) is bytes; assert _ == xbytes('мир')


    # subclass with __str__
    class MyStr(tx):
        def __str__(self): return u'αβγ'
        __unicode__ = __str__
    xx = MyStr(x);  assert type(xx) is MyStr
    _  = tx(xx);    assert type(_)  is tx   ; assert _ == u'αβγ' # unicode(MyStr) -> u'αβγ', not 'мир'
    _  = bstr(xx);  assert type(_)  is bstr ; assert _ == u'αβγ'
    _  = ustr(xx);  assert type(_)  is ustr ; assert _ == u'αβγ'
    _  = b(xx);     assert type(_)  is bstr ; assert _ == u'мир' # b(MyStr) -> 'мир', not 'αβγ'
    _  = u(xx);     assert type(_)  is ustr ; assert _ == u'мир'

    # non-subclass with __str__  (for completeness)
    class MyObj(object):
        def __str__(self):
            return 'myobj'
    xx = MyObj();   assert type(xx) is MyObj
    _  = tx(xx);    assert type(_)  is tx   ; assert _ == 'myobj'
    _  = bstr(xx);  assert type(_)  is bstr ; assert _ == 'myobj'
    _  = ustr(xx);  assert type(_)  is ustr ; assert _ == 'myobj'
    with raises(TypeError): b(xx)   # NOTE b/u reports "convertion failure"
    with raises(TypeError): u(xx)


def test_qq():
    # NOTE qq is also tested as part of strconv.quote

    # qq(any) -> bstr
    def _(s, qqok):
        _ = qq(s)
        assert type(_) is bstr
        assert _ == qqok

    _(      xbytes('мир'),  '"мир"')            # b''
    _(            u'мир',   '"мир"')            # u''
    _(  xbytearray('мир'),  '"мир"')            # bytearray()
    _(           b('мир'),  '"мир"')            # b()
    _(           u('мир'),  '"мир"')            # u()
    _(                  1,  '"1"')              # int
    _(    [xbytes('мир')],  '"[\'мир\']"')      # [b'']
    _(           [u'мир'],  '"[\'мир\']"')      # [u'']
    _([xbytearray('мир')],  '"[\'мир\']"')      # [b'']
    _(         [b('мир')],  '"[\'мир\']"')      # [b()]
    _(         [u('мир')],  '"[\'мир\']"')      # [u()]


    # what qq returns - bstr - can be mixed with both unicode, bytes and bytearray
    # it is tested e.g. in test_strings_ops2 and test_strings_mod_and_format


# ---- bstr/ustr interoperability at CAPI level ----

# verify that PyArg_Parse* handle bstr|ustr correctly.
_ = (
    's',        # s     py2(str|unicode)            py3(str)
    's_star',   # s*    py2(s|buffer)               py3(s|bytes-like)
    's_hash',   # s#    py2(s|r-buffer)             py3(s|r-bytes-like)
    'z',        # z     py2(s|None)                 py3(s|None)
    'z_star',   # z*    py2(z|buffer)               py3(z|bytes-like)
    'z_hash'    # z#    py2(z|r-buffer)             py3(z|r-bytes-like)
)
if six.PY2:
    _ += (
    't_hash',   # t#    py2(r-buffer)
    )
if six.PY3:
    _ += (
    'y',        # y                                 py3(r-bytes-like)
    'y_star',   # y*                                py3(bytes-like)
    'y_hash',   # y#                                py3(r-bytes-like)
    )
# TODO:
#   S   bytes(PyBytesObject)
#   U   unicode(py2:PyUnicodeObject,py3:PyObject)
#   c   (char)
#   C   (py3:unichar)
@mark.parametrize('tx',  (bstr, ustr))
@mark.parametrize('fmt', _)
def test_strings_capi_getargs_to_cstr(tx, fmt):
    if six.PY2:
        if tx is ustr  and  fmt in ('s', 's_star', 's_hash', 'z', 'z_star', 'z_hash', 't_hash'):
            # UnicodeEncodeError: 'ascii' codec can't encode characters in position 0-3: ordinal not in range(128)
            xfail("TODO: py2: PyArg_Parse(%s) vs ustr" % fmt)


    if six.PY3:
        if tx is bstr  and  fmt in ('s', 'z'):
            # PyArg_Parse(s, bstr) currently rejects it with
            #
            #   TypeError: argument 1 must be str, not golang.bstr
            #
            # because internally it insists on the type being PyUnicode_Object and only that.
            # TODO we will try to handle this later
            xfail("TODO: py3: PyArg_Parse(%s) vs bstr" % fmt)

        if tx is ustr  and  fmt in ('s', 's_star', 's_hash', 'z', 'z_star', 'z_hash', 'y', 'y_star', 'y_hash'):
            # UnicodeEncodeError: 'utf-8' codec can't encode character '\udcff' in position 3: surrogates not allowed
            # TypeError: a bytes-like object is required, not 'golang.ustr'
            xfail("TODO: py3: PyArg_Parse(%s) vs ustr" % fmt)

    bmirf = xbytes('мир') + b'\xff'                         # invalid UTF-8 to make sure conversion
    assert bmirf == b'\xd0\xbc\xd0\xb8\xd1\x80\xff'         # takes our codepath instead of builtin
    with raises(UnicodeDecodeError): bmirf.decode('UTF-8')  # UTF-8 decoder/encoder.

    x = xstr(bmirf, tx)
    _ = getattr(testcapi, 'getargs_'+fmt)
    assert _(x) == bmirf



# ---- deep replace ----

# deepReplace returns object's clone with replacing all internal objects selected by predicate.
#
# Specifically: for every object x - obj or its internal object - if
# fpred(x) is true, it is replaced by what freplace(x) returns.
def deepReplace(obj, fpred, freplace):
    r = _DeepReplacer(fpred, freplace)
    return r.replace(obj)

_pickleproto = min(4, pickle.HIGHEST_PROTOCOL) # py2 does not define pickle.DEFAULT_PROTOCOL
_OldClassInstance = None
if six.PY2:
    _OldClassInstance = types.InstanceType

# _DeepReplacer serves deepReplace.
#
# It works by recursively going through objects, unassembling them, doing
# replacements in the unassembled parts, and then rebuilding objects back.
#
# The unassemble/rebuild is implemented via using pickle-related machinery
# (__reduce__ and friends).
class _DeepReplacer:
    def __init__(r, fpred, freplace):
        r.fpred     = fpred
        r.freplace  = freplace
        r.memo      = {}
        r.keepalive = []

        r.rlevel = 0 # recursion level
    def _debug(self, fmt='', *argv):
        if 0:
            print('    '*(self.rlevel-1) + (fmt % argv))

    @func
    def replace(r, obj):
        r.rlevel += 1
        def _(): r.rlevel -= 1
        defer(_)

        r._debug()
        r._debug('_replace %r @%s', obj, id(obj))
        r._debug('  memo:\t%r', r.memo)

        if id(obj) in r.memo:
            r._debug('  (in memo)')
            return r.memo[id(obj)]

        obj_ = r._replace(obj)
        r._debug('-> %r @%s', obj_, id(obj_))

        if id(obj) in r.memo:
            assert r.memo[id(obj)] is obj_
        else:
            r.memo[id(obj)] = obj_

        # keep obj alive while we keep its amended version in memo referenced by id(obj).
        #
        # some objects, that we are processing, might be temporary (i.e. created by ilist/idict)
        # and if we don't keep them alive other temporary objects could be
        # further created with the same id which will break our memo accounting.
        if obj_ is not obj:
            r.keepalive.append(obj)

        return obj_

    def _replace(r, obj):
        if r.fpred(obj):
            return r.freplace(obj)

        cls = type(obj)
        if issubclass(cls, type): # a class, e.g. 'tuple'
            return obj
        # fast path for atomic objects (int, float, bool, bytes, unicode, ... but not e.g. tuple)
        if copy._deepcopy_dispatch.get(cls) is copy._deepcopy_atomic:
            return obj

        # obj is non-atomic - it contains references to other objects
        return r._replace_nonatomic(obj)

    def _replace_nonatomic(r, obj): # -> obj*
        # unassemble and rebuild obj after doing the replacement in its state
        cls = type(obj)

        # handle tuples specially
        # if we don't - we won't get into replacing tuple items, because
        # `tup.__getnewargs__() is (tup,)` and that same tup object will be present in newargv.
        if cls is tuple: # NOTE plain tuple only, no subclasses here
            v = []
            for x in obj:
                x_ = r.replace(x)
                v.append(x_)
            # for self-referencing cases, going replace through the state
            # might already replace the tuple itself
            if id(obj) in r.memo:
                return r.memo[id(obj)]
            return tuple(v)

        if cls is _OldClassInstance: # obj is instance of old-style class
            return r._replace_oldstyle(obj)
        else:
            return r._replace_newstyle(obj)

    def _replace_oldstyle(r, obj): # -> obj*
        # old-style classes are pickled not via __reduce__ - see copy._copy_inst / _deepcopy_inst
        initargv = None
        if hasattr(obj, '__getinitargs__'):
            initargv = obj.__getinitargs__()
        if hasattr(obj, '__getstate__'):
            state = obj.__getstate__()
        else:
            state = obj.__dict__

        # initargv is empty - instantiate the class via _EmptyClass and .__class__ patch
        # https://github.com/python/cpython/blob/2.7-0-g8d21aa21f2c/Lib/pickle.py#L1057-L1059
        if not initargv:
            obj_ = copy._EmptyClass()
            obj_.__class__ = obj.__class__
            assert id(obj) not in r.memo
            r.memo[id(obj)] = obj_

        # initargv
        if initargv is not None:
            initargv_ = []
            for x in initargv:
                x_, n = r.replace(x)
                initargv_.append(x_)
            initargv = tuple(initargv_)

        # state
        state = r.replace(state)

        if initargv is not None:
            obj_ = obj.__class__(*initargv)
        else:
            obj_ = r.memo[id(obj)]

        if hasattr(obj_, '__setstate__'):
            obj_.__setstate__(state)
        else:
            obj_.__dict__.update(state)

        return obj_


    def _replace_newstyle(r, obj): # -> obj*
        # new-style classes are pickled via __reduce__
        # see copy and pickle documentation for details
        # https://docs.python.org/3/library/pickle.html#pickling-class-instances
        state = None
        ilist = None
        idict = None
        setstate = None

        # TODO copy_reg.reduce should have priority ?
        _ = obj.__reduce_ex__(_pickleproto)

        new     = _[0]
        newargv = _[1]
        if len(_) >= 3:
            state = _[2]
        if len(_) >= 4:
            ilist = _[3]
        if len(_) >= 5:
            idict = _[4]
        if len(_) >= 6:
            setstate = _[5]

        r._debug()
        r._debug('  obj:\t%r @%s', obj, id(obj))
        r._debug('  new:\t%r', new)
        r._debug('  newargv: %r', newargv)
        r._debug('  state:\t%r', state)
        r._debug('  ilist:\t%r', ilist)
        r._debug('  idict:\t%r', idict)
        r._debug('  setstate:\t%r', setstate)

        # __newobj__ function is treated specially meaning __newobj__(cls) should call cls.__new__()
        # https://github.com/python/cpython/blob/v3.11.0a7-248-g4153f2cbcb4/Lib/pickle.py#L652-L689
        new_name = getattr(new, "__name__", "")
        if new_name == "__newobj__" and len(newargv) == 1:
            cls = newargv[0]
            if hasattr(cls, "__new__"):
                assert id(obj) not in r.memo
                r.memo[id(obj)] = cls.__new__(cls)

        # newargv
        newargv_ = []
        for x in newargv:
            x_ = r.replace(x)
            newargv_.append(x_)
        newargv = tuple(newargv_)

        # state
        if state is not None:
            state = r.replace(state)

        # ilist
        if ilist is not None:
            ilist_ = []
            for x in ilist:
                x_ = r.replace(x)
                ilist_.append(x_)
            ilist = ilist_  # NOTE unconditionally (we consumed the iterator)

        # idict
        if idict is not None:
            idict_ = []
            for x in idict:
                x_ = r.replace(x)
                idict_.append(x_)
            idict = idict_  # NOTE unconditionally (----//----)


        # for self-referencing cases, going replace through arguments/state
        # might already replace the object itself
        if id(obj) in r.memo:
            obj_ = r.memo[id(obj)]
        else:
            obj_ = new(*newargv)

        if state is not None:
            if setstate is not None:
                setstate(obj_, state)
            elif hasattr(obj_, '__setstate__'):
                obj_.__setstate__(state)
            else:
                obj_.__dict__.update(state)

        if ilist is not None:
            for _ in ilist:
                obj_.append(_)

        if idict is not None:
            for k,v in idict:
                obj_[k] = v

        return obj_


# deepReplaceBytes returns obj's clone with bytes instances replaced with
# unicode via UTF-8 decoding.
def _isxbytes(x):
    if not isinstance(x, bytes):
        return False
    return True
def _bdecode(x):
    return _udata(u(x))
def deepReplaceBytes(obj):
    return deepReplace(obj, _isxbytes, _bdecode)


def test_deepreplace_bytes():
    def f(): pass
    g = lambda: None # non-picklable func
    with raises((pickle.PicklingError, AttributeError), match="Can't pickle "):
        pickle.dumps(g, pickle.HIGHEST_PROTOCOL)

    class L(list):      pass
    class T(tuple):     pass
    class S(set):       pass
    class F(frozenset): pass
    class D(dict):      pass

    class Cold: pass
    class Cnew(object): pass

    # TODO class without reduce, but that can be reduced via copy_reg
    # TODO class completely without reduce support

    cold = Cold(); cold.x = u"α"
    cnew = Cnew(); cnew.x = u"β"

    nochangev = [
        1001, 123.4, complex(1,2), None, True, False,
        u"α",
        f, g,
        type,
        unicode, bytes,
        tuple, list, int, dict,
        Cold, Cnew,
        NotImplementedError,
        [], (), {}, set(), frozenset(),
        [1, u"α", f],               L([1, u"α", f]),
        (1, u"α", g),               T([1, u"α", g]),
        {1, u"α", f},               S({1, u"α", f}),
        frozenset({1, u"α", f}),    F({1, u"α", f}),
        {1:2, u"α":u"β", f:g},      D({1:2, u"α":u"β", f:g}),
        #cold, cnew,
        [(u"α", {u"β":2, 3:[4, {u"γ"}]})],
    ]
    for x in nochangev:
        assert deepReplaceBytes(x) == x

    bs = xbytes("мир")      ; assert type(bs) is bytes
    us = xunicode("мир")    ; assert type(us) is unicode

    _ = deepReplaceBytes(bs)
    assert type(_) is unicode
    assert _ == us

    x = 123
    def R(obj):
        obj_ = deepReplaceBytes(obj)
        assert type(obj_) is type(obj)
        return obj_

    # list
    for typ in (list, L):
        assert R(typ([bs])) == typ([us])

        _ = R(typ([x, bs, f]))
        assert _ == typ([x, us, f])
        assert _[0] is x
        assert _[2] is f

        _ = R(typ([bs, [bs]]))  # verify that last bs is not missed to be converted due to memoization
        assert _ == typ([us, [us]])

        l = typ();  l += [l]        # self-reference, nochange
        _ = R(l)
        assert len(_) == 1
        assert _[0] is _

        l = typ([bs]); l += [l, bs] # self-reference
        _ = R(l)
        assert len(_) == 3
        assert _[0] == us
        assert _[1] is _
        assert _[2] == us

    # tuple
    for typ in (tuple, T):
        assert R(typ((bs,))) == typ((us,))

        _ = R(typ((x, bs, f)))
        assert _ == typ((x, us, f))
        assert _[0] is x
        assert _[2] is f

        t = typ(([],));  t[0].append(t)     # self-reference, nochange
        _ = R(t)
        assert len(_) == 1
        assert len(_[0]) == 1
        assert _[0][0] is _

        t = typ(([bs], bs)); t[0].append(t) # self-reference
        _ = R(t)
        assert len(_) == 2
        assert len(_[0]) == 2
        assert _[0][0] == us
        assert _[0][1] is _
        assert _[1] == us

    # set
    for typ in (set, frozenset, S, F):
        assert R(typ({bs})) == typ({us})

        _ = R(typ({x, bs, f}))
        assert _ == typ({x, us, f})
        _ = set(_) # e.g. frozenset -> set
        _.remove(us)
        while _:
            obj = _.pop()
            if   obj == x:  assert obj is x
            elif obj == f:  assert obj is f
            else: panic(obj)

        l = hlist();  s = typ({l}); l.append(s)         # self-reference, nochange
        s_ = R(s)
        assert len(s_) == 1
        l_ = list(s_)[0]
        assert type(l_) is hlist
        assert len(l_) == 1
        assert l_[0] is s_

        l = hlist();  s = typ({bs, l});  l.append(s)    # self-reference
        s_ = R(s)
        assert len(s_) == 2
        _ = list(s_)
        assert us in _
        obj = _.pop(_.index(us))
        assert type(obj) is unicode
        assert obj == us
        assert len(_) == 1
        assert type(_[0]) is hlist
        assert len(_[0])  == 1
        assert _[0][0] is s_

    # dict
    for typ in (dict, D):
        _ = R(typ({x:bs, bs:12, f:g}))
        assert _ == typ({x:us, us:12, f:g})

        l = hlist([x]);  d = typ({l:12});  l.append(d)  # self-reference(value), nochange
        d_ = R(d)
        _ = list(d_.items())
        assert len(_) == 1
        l_, v = _[0]
        assert v == 12
        assert type(l_) is hlist
        assert len(l_)  == 2
        assert l_[0] == x
        assert l_[1] is d_

        l = hlist([x]);  d = typ({12:l});  l.append(d)  # self-reference(value), nochange
        d_ = R(d)
        _ = list(d_.items())
        assert len(_) == 1
        k, l_ = _[0]
        assert k == 12
        assert type(l_) is hlist
        assert len(l_)  == 2
        assert l_[0] == x
        assert l_[1] is d_

        lk = hlist([x]);  lv = hlist([12]);  d = typ({lk:lv})   # self-ref(key,value), nochange
        lk.append(d);     lv.append(d)
        d_ = R(d)
        _ = list(d_.items())
        assert len(_) == 1
        lk_, lv_ = _[0]
        assert type(lk_) is hlist
        assert type(lv_) is hlist
        assert len(lk_) == 2
        assert len(lv_) == 2
        assert lk_[0] == x
        assert lv_[0] == 12
        assert lk_[1] is d_
        assert lv_[1] is d_

        lk = hlist([xbytes('key')]);  lv = hlist([xbytes('value')]);  d = typ({lk:lv}) # self-ref(k,v)
        lk.append(d);                 lv.append(d)
        d_ = R(d)
        _ = list(d_.items())
        assert len(_) == 1
        lk_, lv_ = _[0]
        assert type(lk_) is hlist
        assert type(lv_) is hlist
        assert len(lk_) == 2
        assert len(lv_) == 2
        assert type(lk_[0]) is unicode
        assert type(lv_[0]) is unicode
        assert lk_[0] == xunicode('key')
        assert lv_[0] == xunicode('value')
        assert lk_[1] is d_
        assert lv_[1] is d_


    # class instances
    cold = Cold();  cold.x = x;  cold.y = bs;  cold.me = cold
    cnew = Cnew();  cnew.f = f;  cnew.y = bs;  cnew.me = cnew

    _ = R(cold)
    assert _ is not cold
    assert _.x  is x
    assert _.y  == us
    assert _.me is _

    _ = R(cnew)
    assert _ is not cnew
    assert _.f  is f
    assert _.y  == us
    assert _.me is _


    # combining example
    cnew = Cnew()
    cnew.a = [cnew, {bs}]
    cnew.b = {(bs,f): g}

    _ = R(cnew)
    assert _ is not cnew
    assert type(_.a) is list
    assert len(_.a)  == 2
    assert _.a[0] is _
    assert type(_.a[1]) is set
    assert _.a[1] == {us}
    assert type(_.b) is dict
    assert len(_.b) == 1
    k, v = list(_.b.items())[0]
    assert type(k) is tuple
    assert len(k)  == 2
    assert type(k[0]) is unicode
    assert k[0] == us
    assert k[1] is f
    assert v is g


# deepReplaceStr returns x with all instances of str replaced with bstrmk(·)
#
# except as ad-hoc rule we we don't change ASCII strings to avoid changing
# e.g. __dict__ keys in classes from str to bytes. However a string can be
# forced to be processed as string and changed - even if it is all ASCII - by
# starting it with "*str " prefix.
def _isstr(x):
    return (type(x) is str) and (x.startswith("*str ") or not isascii(x))
def deepReplaceStr(x, bstrmk):
    return deepReplace(x, _isstr, bstrmk)

def test_deepreplace_str():
    # verify deepReplaceStr only lightly because underlying deepReplace
    # functionality is verified thoroughly via test_deepreplace_bytes
    _ = deepReplaceStr('α', b)
    assert type(_) is bstr
    assert _ == 'α'
    _ = deepReplaceStr('β', u)
    assert type(_) is ustr
    assert _ == 'β'

    def R(x):
        x_ = deepReplaceStr(x, b)
        assert type(x_) is type(x)
        return x_

    x = 123
    assert R(x) is x

    _ = R([1, 'α', 2])
    assert _ == [1, 'α', 2]
    assert type(_[1]) is bstr


# ----------------------------------------

# verify that what we patched - e.g. bytes.__repr__ - stay unaffected when
# called outside of bstr/ustr context.
def test_strings_patched_transparently():
    b_  = xbytes    ("мир");  assert type(b_)  is bytes
    u_  = xunicode  ("мир");  assert type(u_)  is unicode
    ba_ = xbytearray("мир");  assert type(ba_) is bytearray

    # standard {repr,str}(bytes|unicode|bytearray) stay unaffected
    assert repr(b_)  == x32(r"b'\xd0\xbc\xd0\xb8\xd1\x80'",
                             r"'\xd0\xbc\xd0\xb8\xd1\x80'")
    assert repr(u_)  == x32(r"'мир'",
                            r"u'\u043c\u0438\u0440'")
    assert repr(ba_) == r"bytearray(b'\xd0\xbc\xd0\xb8\xd1\x80')"

    assert str(b_)   == x32(r"b'\xd0\xbc\xd0\xb8\xd1\x80'",
                               "\xd0\xbc\xd0\xb8\xd1\x80")
    if six.PY3  or  sys.getdefaultencoding() == 'utf-8': # py3 or gpython/py2
        assert str(u_) == "мир"
    else:
        # python/py2
        with raises(UnicodeEncodeError): str(u_)  # 'ascii' codec can't encode ...
        assert str(u'abc') == "abc"

    assert str(ba_)  == x32(r"bytearray(b'\xd0\xbc\xd0\xb8\xd1\x80')",
                                        b'\xd0\xbc\xd0\xb8\xd1\x80')

    # unicode comparison stay unaffected
    assert (u_ == u_)  is True
    assert (u_ != u_)  is False
    assert (u_ <  u_)  is False
    assert (u_ >  u_)  is False
    assert (u_ <= u_)  is True
    assert (u_ >= u_)  is True

    u2 = xunicode("май");  assert type(u2) is unicode
    assert (u_ == u2)  is False     ; assert (u2 == u_)  is False
    assert (u_ != u2)  is True      ; assert (u2 != u_)  is True
    assert (u_ <  u2)  is False     ; assert (u2 <  u_)  is True
    assert (u_ >  u2)  is True      ; assert (u2 >  u_)  is False
    assert (u_ <= u2)  is False     ; assert (u2 <= u_)  is True
    assert (u_ >= u2)  is True      ; assert (u2 >= u_)  is False

    # bytearray.__init__ stay unaffected
    with raises(TypeError): bytearray(u'мир')
    a = bytearray()
    with raises(TypeError): a.__init__(u'мир')

    def _(*argv):
        a = bytearray(*argv)
        b = bytearray(); _ = b.__init__(*argv); assert _ is None
        ra = repr(a)
        rb = repr(b)
        assert ra == rb
        return ra

    assert _()              == r"bytearray(b'')"
    assert _(b_)            == r"bytearray(b'\xd0\xbc\xd0\xb8\xd1\x80')"
    assert _(u_, 'utf-8')   == r"bytearray(b'\xd0\xbc\xd0\xb8\xd1\x80')"
    assert _(3)             == r"bytearray(b'\x00\x00\x00')"
    assert _((1,2,3))       == r"bytearray(b'\x01\x02\x03')"

    # bytearray.{sq_concat,sq_inplace_concat} stay unaffected
    a = bytearray()
    def _(delta):
        aa  = a + delta
        aa_ = a.__add__(delta)
        assert aa  is not a
        assert aa_ is not a
        aclone = bytearray(a)
        a_ = a
        a_ += delta
        aclone_ = aclone
        aclone_.__iadd__(delta)
        assert a_ is a
        assert a_ == aa
        assert aclone_ is aclone
        assert aclone_ == a_
        return a_
    assert _(b'')       == b''
    assert _(b'a')      == b'a'
    assert _(b'b')      == b'ab'
    assert _(b'cde')    == b'abcde'


# ---- issues hit by users ----
# fixes for below issues have their corresponding tests in the main part above, but
# we also add tests with original code where problems were hit.

# three-way comparison wrt class with __cmp__ was working incorrectly because
# bstr.__op__ were not returning NotImplemented wrt non-string types.
# https://lab.nexedi.com/nexedi/slapos/-/merge_requests/1575#note_206080
@mark.parametrize('tx', (str, bstr if str is bytes  else ustr)) # LooseVersion does not handle unicode on py2
def test_strings_cmp_wrt_distutils_LooseVersion(tx):
    from distutils.version import LooseVersion

    l = LooseVersion('1.16.2')

    x = xstr('1.12', tx)
    assert not (x == l)
    assert not (l == x)
    assert      x != l
    assert      l != x
    assert not (x >= l)
    assert      l >= x
    assert      x <= l
    assert not (l <= x)
    assert      x < l
    assert not (l < x)

    x = xstr('1.16.2', tx)
    assert      x == l
    assert      l == x
    assert not (x != l)
    assert not (l != x)
    assert      x >= l
    assert      l >= x
    assert      x <= l
    assert      l <= x
    assert not (x < l)
    assert not (l < x)


# ---- benchmarks ----

# utf-8 decoding
def bench_stddecode(b):
    s = xbytes(u'α'*100)
    for i in xrange(b.N):
        s.decode('utf-8')

def bench_udecode(b):
    s = xbytes(u'α'*100)
    uu = golang.u
    for i in xrange(b.N):
        uu(s)

# utf-8 encoding
def bench_stdencode(b):
    s = u'α'*100
    for i in xrange(b.N):
        s.encode('utf-8')

def bench_bencode(b):
    s = u'α'*100
    bb = golang.b
    for i in xrange(b.N):
        bb(s)


# ---- misc ----

# xbytes/xunicode/xbytearray convert provided bytes/unicode object to bytes,
# unicode or bytearray correspondingly to function name.
def xbytes(x):
    assert isinstance(x, (bytes,unicode))
    if isinstance(x, unicode):
        x = x.encode('utf-8')
    assert isinstance(x, bytes)
    x = _bdata(x)
    assert type(x) is bytes
    return x

def xunicode(x):
    assert isinstance(x, (bytes,unicode))
    if isinstance(x, bytes):
        x = x.decode('utf-8')
    assert isinstance(x, unicode)
    x = _udata(x)
    assert type(x) is unicode
    return x

def xbytearray(x):
    assert isinstance(x, (bytes,unicode))
    x = bytearray(xbytes(x))
    assert type(x) is bytearray
    return x

# deepReplaceStr2Bytearray replaces str to bytearray, or hashable-version of
# bytearray, if str objects are detected to be present inside set or dict keys.
class hbytearray(bytearray):
    def __hash__(self):
        return hash(bytes(self))
def xhbytearray(x): return hbytearray(xbytes(x))
def deepReplaceStr2Bytearray(x):
    try:
        return deepReplaceStr(x, xbytearray)
    except TypeError as e:
        if e.args != ("unhashable type: 'bytearray'",):
            raise
        return deepReplaceStr(x, xhbytearray)

# xstr returns string corresponding to specified type and data.
def xstr(text, typ):
    def _():
        t = {
            bytes:      xbytes,
            unicode:    xunicode,
            bytearray:  xbytearray,
            bstr:       b,
            ustr:       u,
        }
        return t[typ](text)
    s = _()
    assert type(s) is typ
    return s

# xudata returns data of x converted to unicode string.
# x can be bytes/unicode/bytearray / bstr/ustr.
def xudata(x):
    def _():
        if type(x) in (bytes, bytearray):
            return x.decode('utf-8')
        elif type(x) is unicode:
            return x
        elif type(x) is ustr:
            return _udata(x)
        elif type(x) is bstr:
            return _bdata(x).decode('utf-8')
        else:
            raise TypeError(x)
    xu = _()
    assert type(xu) is unicode
    return xu


# tbu maps specified type to b/u:
# b/bytes/bytearray -> b; u/unicode -> u.
def tbu(typ):
    if typ in (bytes, bytearray, bstr):
        return bstr
    if typ in (unicode, ustr):
        return ustr
    raise AssertionError("invalid type %r" % typ)

# xcall returns result of the call to `obj.meth(*argv, **kw)`.
# exceptions are also converted to plain returns.
def xcall(obj, meth, *argv, **kw):
    if not hasattr(obj, meth):
        return NotImplementedError(meth)
    meth = getattr(obj, meth)
    try:
        return meth(*argv, **kw)
    except Exception as e:
        #traceback.print_exc()
        return e

# isascii returns whether bytes/unicode x consists of only ASCII characters.
def isascii(x):
    if isinstance(x, unicode):
        x = x.encode('utf-8')
    assert isinstance(x, bytes)

    # hand-made isascii (there is no bytes.isascii on py2)
    try:
        bytes.decode(x, 'ascii', 'strict')
    except UnicodeDecodeError:
        return False # non-ascii
    else:
        return True  # ascii

# hlist is hashable list.
class hlist(list):
    def __hash__(self):
        return 0    # always hashable

# x32(a,b) returns a on py3, or b on py2
def x32(a, b):
    return a if six.PY3 else b
