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

import golang
from golang import b, u, bstr, ustr
from golang._golang import _udata, _bdata
from golang.gcompat import qq
from golang.strconv_test import byterange
from golang.golang_test import readfile, assertDoc, _pyrun, dir_testprog, PIPE
from pytest import raises, mark, skip
import sys
import six
from six import text_type as unicode
from six.moves import range as xrange
import array


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


    # b/u accept only ~bytes/~unicode/bytearray
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
    _ = bstr([1,'b']);  assert type(_) is bstr;  assert _ == "[1, 'b']"
    _ = ustr([1,'b']);  assert type(_) is ustr;  assert _ == "[1, 'b']"
    obj = object()
    _ = bstr(obj);      assert type(_) is bstr;  assert _ == str(obj)  # <object ...>
    _ = ustr(obj);      assert type(_) is ustr;  assert _ == str(obj)  # <object ...>


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

    # bytes(b(·)) = identity,   unicode(u(·)) = identity
    assert bytes  (bs) is bs
    assert unicode(us) is us

    # unicode(b) -> u,  bytes(u) -> b
    _ = unicode(bs);  assert type(_) is ustr;  assert _ == "мир"
    _ = bytes  (us);  assert type(_) is bstr;  assert _ == "мир"

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

    # str
    _ = str(us);   assert isinstance(_, str);  assert _ == "мир"
    _ = str(bs);   assert isinstance(_, str);  assert _ == "мир"

    # custom attributes cannot be injected to bstr/ustr
    if not ('PyPy' in sys.version): # https://foss.heptapod.net/pypy/pypy/issues/2763
        with raises(AttributeError):
            us.hello = 1
        with raises(AttributeError):
            bs.hello = 1


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
        with raises(TypeError): x >= y
        with raises(TypeError): x <= y
        with raises(TypeError): x >  y
        with raises(TypeError): x <  y
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

# verify print for bstr/ustr.
def test_strings_print():
    outok = readfile(dir_testprog + "/golang_test_str.txt")
    retcode, stdout, stderr = _pyrun(["golang_test_str.py"],
                                cwd=dir_testprog, stdout=PIPE, stderr=PIPE)
    assert retcode == 0, (stdout, stderr)
    assert stderr == b""
    assertDoc(outok, stdout)


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

    # qq(any) returns string type
    assert isinstance(qq(b('мир')), str)    # qq(b) -> str (bytes·py2, unicode·py3)
    assert isinstance(qq( u'мир'),  str)    # qq(u) -> str (bytes·py2, unicode·py3)

    # however what qq returns can be mixed with both unicode and bytes
    assert b'hello %s !' % qq(b('мир')) == b('hello "мир" !')   # b % qq(b)
    assert b'hello %s !' % qq(u('мир')) == b('hello "мир" !')   # b % qq(u) -> b
    assert u'hello %s !' % qq(u('мир')) == u('hello "мир" !')   # u % qq(u)
    assert u'hello %s !' % qq(b('мир')) ==  u'hello "мир" !'    # u % qq(b) -> u


# ----------------------------------------

# verify that what we patched stay unaffected when
# called outside of bstr/ustr context.
def test_strings_patched_transparently():
    b_  = xbytes    ("мир");  assert type(b_)  is bytes
    u_  = xunicode  ("мир");  assert type(u_)  is unicode

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
def xbytes(x):     return x.encode('utf-8') if type(x) is unicode else x
def xunicode(x):   return x.decode('utf-8') if type(x) is bytes   else x
def xbytearray(x): return bytearray(xbytes(x))

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
