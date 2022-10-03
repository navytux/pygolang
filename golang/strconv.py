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
"""Package strconv provides Go-compatible string conversions."""

from __future__ import print_function, absolute_import

import unicodedata, codecs
from six import text_type as unicode        # py2: unicode      py3: str
from six.moves import range as xrange

from golang import b, u
from golang._golang import _utf8_decode_rune, _rune_error, _xunichr


# _bstr is like b but also returns whether input was unicode.
def _bstr(s):   # -> sbytes, wasunicode
    return b(s), isinstance(s, unicode)

# _ustr is like u but also returns whether input was bytes.
def _ustr(s):   # -> sunicode, wasbytes
    return u(s), isinstance(s, bytes)


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
            if r == _rune_error  and  size == 1:
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
