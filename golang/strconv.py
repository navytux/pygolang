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
from six.moves import range as xrange

from golang import b
from golang._golang import _py_utf8_decode_rune as _utf8_decode_rune, _py_rune_error as _rune_error, _xunichr


# quote quotes unicode|bytes string into valid "..." bytestring always quoted with ".
def quote(s):  # -> bstr
    q, _ = _quote(b(s), b'"')
    return b(q)

def _quote(s, quote): # -> (quoted, nonascii_escape)
    assert isinstance(s, bytes),     type(s)
    assert isinstance(quote, bytes), type(quote)
    assert len(quote) == 1,          repr(quote)

    outv = []
    emit = outv.append
    nonascii_escape = False
    i = 0
    while i < len(s):
        c = s[i:i+1]
        # fast path - ASCII only
        if ord(c) < 0x80:
            if c in (b'\\', quote):
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
                nonascii_escape = True
                emit(br'\x%02x' % ord(c))

            # printable utf-8 characters go as is
            elif unicodedata.category(_xunichr(r))[0] in _printable_cat0:
                emit(s[i:isize])

            # everything else goes in numeric byte escapes
            else:
                nonascii_escape = True
                for j in xrange(i, isize):
                    emit(br'\x%02x' % ord(s[j:j+1]))

            i = isize

    return (quote + b''.join(outv) + quote, nonascii_escape)


# unquote decodes "-quoted unicode|byte string.
#
# ValueError is raised if there are quoting syntax errors.
def unquote(s):  # -> bstr
    us, tail = unquote_next(s)
    if len(tail) != 0:
        raise ValueError('non-empty tail after closing "')
    return us

# unquote_next decodes next "-quoted unicode|byte string.
#
# it returns -> (unquoted(s), tail-after-")
#
# ValueError is raised if there are quoting syntax errors.
def unquote_next(s):  # -> (bstr, bstr)
    us, tail = _unquote_next(b(s))
    return b(us), b(tail)

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
