# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021  Nexedi SA and Contributors.
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
"""Package strconv provides Go-compatible string conversions."""

from __future__ import print_function, absolute_import

import sys
import six, unicodedata, codecs
from six import text_type as unicode        # py2: unicode      py3: str
from six import unichr                      # py2: unichr       py3: chr
from six import int2byte as bchr            # py2: chr          py3: lambda x: bytes((x,))
from six.moves import range as xrange


# _bstr is like b but also returns whether input was unicode.
def _bstr(s):   # -> sbytes, wasunicode
    wasunicode = False
    if isinstance(s, bytes):                    # py2: str      py3: bytes
        pass
    elif isinstance(s, unicode):                # py2: unicode  py3: str
        wasunicode = True
    else:
        raise TypeError("b: invalid type %s" % type(s))

    if wasunicode:                              # py2: unicode  py3: str
        if six.PY3:
            s = s.encode('UTF-8', 'surrogateescape')
        else:
            # py2 does not have surrogateescape error handler, and even if we
            # provide one, builtin unicode.encode() does not treat
            # \udc80-\udcff as error. -> Do the encoding ourselves.
            s = _utf8_encode_surrogateescape(s)

    return s, wasunicode

# _ustr is like u but also returns whether input was bytes.
def _ustr(s):   # -> sunicode, wasbytes
    wasbytes = True
    if isinstance(s, bytes):                    # py2: str      py3: bytes
        pass
    elif isinstance(s, unicode):                # py2: unicode  py3: str
        wasbytes = False
    else:
        raise TypeError("u: invalid type %s" % type(s))

    if wasbytes:
        if six.PY3:
            s = s.decode('UTF-8', 'surrogateescape')
        else:
            # py2 does not have surrogateescape error handler, and even if we
            # provide one, builtin bytes.decode() does not treat surrogate
            # sequences as error. -> Do the decoding ourselves.
            s = _utf8_decode_surrogateescape(s)

    return s, wasbytes


# quote quotes unicode|bytes string into valid "..." unicode|bytes string always quoted with ".
def quote(s):
    s, wasunicode = _bstr(s)
    qs = _quote(s)
    if wasunicode:
        qs, _ = _ustr(qs)
    return qs

def _quote(s):
    assert isinstance(s, bytes)

    outv = []
    emit = outv.append
    i = 0
    while i < len(s):
        c = s[i:i+1]
        # fast path - ASCII only
        if ord(c) < 0x80:
            if c in b'\\"':
                emit(b'\\'+c)

            # printable ASCII
            elif b' ' <= c <= b'\x7e':
                emit(c)

            # non-printable ASCII
            elif c == b'\t':
                emit(br'\t')
            elif c == b'\n':
                emit(br'\n')
            elif c == b'\r':
                emit(br'\r')

            # everything else is non-printable
            else:
                emit(br'\x%02x' % ord(c))

            i += 1

        # slow path - full UTF-8 decoding + unicodedata
        else:
            r, size = _utf8_decode_rune(s[i:])
            isize = i + size

            # decode error - just emit raw byte as escaped
            if r == _rune_error:
                emit(br'\x%02x' % ord(c))

            # printable utf-8 characters go as is
            elif unicodedata.category(_xunichr(r))[0] in _printable_cat0:
                emit(s[i:isize])

            # everything else goes in numeric byte escapes
            else:
                for j in xrange(i, isize):
                    emit(br'\x%02x' % ord(s[j:j+1]))

            i = isize

    return b'"' + b''.join(outv) + b'"'


# unquote decodes "-quoted unicode|byte string.
#
# ValueError is raised if there are quoting syntax errors.
def unquote(s):
    us, tail = unquote_next(s)
    if len(tail) != 0:
        raise ValueError('non-empty tail after closing "')
    return us

# unquote_next decodes next "-quoted unicode|byte string.
#
# it returns -> (unquoted(s), tail-after-")
#
# ValueError is raised if there are quoting syntax errors.
def unquote_next(s):
    s, wasunicode = _bstr(s)
    us, tail = _unquote_next(s)
    if wasunicode:
        us, _   = _ustr(us)
        tail, _ = _ustr(tail)
    return us, tail

def _unquote_next(s):
    assert isinstance(s, bytes)

    if len(s) == 0 or s[0:0+1] != b'"':
        raise ValueError('no starting "')

    outv = []
    emit= outv.append

    s = s[1:]
    while 1:
        r, width = _utf8_decode_rune(s)
        if width == 0:
            raise ValueError('no closing "')

        if r == ord('"'):
            s = s[1:]
            break

        # regular UTF-8 character
        if r != ord('\\'):
            emit(s[:width])
            s = s[width:]
            continue

        if len(s) < 2:
            raise ValueError('unexpected EOL after \\')

        c = s[1:1+1]

        # \<c> -> <c>   ; c = \ "
        if c in b'\\"':
            emit(c)
            s = s[2:]
            continue

        # \t \n \r
        uc = None
        if   c == b't':  uc = b'\t'
        elif c == b'n':  uc = b'\n'
        elif c == b'r':  uc = b'\r'
        # accept also \a \b \v \f that Go might produce
        # Python also decodes those escapes even though it does not produce them:
        # https://github.com/python/cpython/blob/2.7.18-0-g8d21aa21f2c/Objects/stringobject.c#L677-L688
        elif c == b'a':  uc = b'\x07'
        elif c == b'b':  uc = b'\x08'
        elif c == b'v':  uc = b'\x0b'
        elif c == b'f':  uc = b'\x0c'

        if uc is not None:
            emit(uc)
            s = s[2:]
            continue

        # \x?? hex
        if c == b'x':   # XXX also handle octals?
            if len(s) < 2+2:
                raise ValueError('unexpected EOL after \\x')

            b = codecs.decode(s[2:2+2], 'hex')
            emit(b)
            s = s[2+2:]
            continue

        raise ValueError('invalid escape \\%s' % chr(ord(c[0:0+1])))

    return b''.join(outv), s


_printable_cat0 = frozenset(['L', 'N', 'P', 'S'])   # letters, numbers, punctuation, symbols

_rune_error = 0xFFFD # unicode replacement character

_ucs2_build        = (sys.maxunicode ==     0xffff)     #    ucs2
assert _ucs2_build or sys.maxunicode >= 0x0010ffff      # or ucs4

# _utf8_decode_rune decodes next UTF8-character from byte string s.
#
# _utf8_decode_rune(s) -> (r, size)
def _utf8_decode_rune(s):
    assert isinstance(s, bytes)

    if len(s) == 0:
        return _rune_error, 0

    l = min(len(s), 4)  # max size of an UTF-8 encoded character
    while l > 0:
        try:
            r = s[:l].decode('utf-8', 'strict')
        except UnicodeDecodeError:
            l -= 1
            continue

        if len(r) == 1:
            return ord(r), l

        # see comment in _utf8_encode_surrogateescape
        if _ucs2_build and len(r) == 2:
            try:
                return _xuniord(r), l
            # e.g. TypeError: ord() expected a character, but string of length 2 found
            except TypeError:
                l -= 1
                continue

        l -= 1
        continue

    # invalid UTF-8
    return _rune_error, 1


# _utf8_decode_surrogateescape mimics s.decode('utf-8', 'surrogateescape') from py3.
def _utf8_decode_surrogateescape(s): # -> unicode
    assert isinstance(s, bytes)
    outv = []
    emit = outv.append

    while len(s) > 0:
        r, width = _utf8_decode_rune(s)
        if r == _rune_error:
            b = ord(s[0])
            assert 0x80 <= b <= 0xff
            emit(unichr(0xdc00 + b))

        # python2 "correctly" decodes surrogates - don't allow that as
        # surrogates are not valid UTF-8:
        # https://github.com/python/cpython/blob/v3.8.1-118-gdbb37aac142/Objects/stringlib/codecs.h#L153-L157
        # (python3 raises UnicodeDecodeError for surrogates)
        elif 0xd800 <= r < 0xdfff:
            for c in s[:width]:
                b = ord(c)
                if c >= 0x80:
                    emit(unichr(0xdc00 + b))
                else:
                    emit(unichr(b))

        else:
            emit(_xunichr(r))

        s = s[width:]

    return u''.join(outv)


# _utf8_encode_surrogateescape mimics s.encode('utf-8', 'surrogateescape') from py3.
def _utf8_encode_surrogateescape(s): # -> bytes
    assert isinstance(s, unicode)
    outv = []
    emit = outv.append

    while len(s) > 0:
        uc = s[0]; s = s[1:]
        c = ord(uc)

        if 0xdc80 <= c <= 0xdcff:
            # surrogate - emit unescaped byte
            emit(bchr(c & 0xff))
            continue

        # in builds with --enable-unicode=ucs2 (default for py2 on macos and windows)
        # python represents unicode points > 0xffff as _two_ unicode characters:
        #
        #   uh = u - 0x10000
        #   c1 = 0xd800 + (uh >> 10)      ; [d800, dbff]
        #   c2 = 0xdc00 + (uh & 0x3ff)    ; [dc00, dfff]
        #
        # if detected - merge those two unicode characters for .encode('utf-8') below
        #
        # this should be only relevant for python2, as python3 switched to "flexible"
        # internal unicode representation: https://www.python.org/dev/peps/pep-0393
        if _ucs2_build and (0xd800 <= c <= 0xdbff):
            if len(s) > 0:
                uc2 = s[0]
                c2 = ord(uc2)
                if 0xdc00 <= c2 <= 0xdfff:
                    uc = uc + uc2
                    s = s[1:]

        emit(uc.encode('utf-8', 'strict'))

    return b''.join(outv)


# _xuniord returns ordinal for a unicode character u.
#
# it works correctly even if u is represented as 2 unicode surrogate points on
# ucs2 python build.
if not _ucs2_build:
    _xuniord = ord
else:
    def _xuniord(u):
        assert isinstance(u, unicode)
        if len(u) == 1:
            return ord(u)

        # see _utf8_encode_surrogateescape for details
        if len(u) == 2:
            c1 = ord(u[0])
            c2 = ord(u[1])
            if (0xd800 <= c1 <= 0xdbff) and (0xdc00 <= c2 <= 0xdfff):
                return 0x10000 | ((c1 - 0xd800) << 10) | (c2 - 0xdc00)

        # let it crash
        return ord(u)


# _xunichr returns unicode character for an ordinal i.
#
# it works correctly even on ucs2 python builds, where ordinals >= 0x10000 are
# represented as 2 unicode pointe.
if not _ucs2_build:
    _xunichr = unichr
else:
    def _xunichr(i):
        if i < 0x10000:
            return unichr(i)

        # see _utf8_encode_surrogateescape for details
        uh = i - 0x10000
        return unichr(0xd800 + (uh >> 10)) + \
               unichr(0xdc00 + (uh & 0x3ff))
