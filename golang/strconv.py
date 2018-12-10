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
"""Package strconv provides Go-compatible string conversions"""

import six, unicodedata, codecs
from six.moves import range as xrange


# _bstr converts str/unicode/bytes s to UTF-8 encoded bytestring.
#
# TypeError is raised if type(s) is not one of the above.
def _bstr(s):   # -> sbytes, wasunicode
    wasunicode = False
    if isinstance(s, bytes):                    # py2: str      py3: bytes
        pass
    elif isinstance(s, six.text_type):          # py2: unicode  py3: str
        wasunicode = True
    else:
        raise TypeError("_bstr: invalid type %s", type(s))

    if wasunicode:                              # py2: unicode  py3: str    -> bytes
        s = s.encode('UTF-8')

    return s, wasunicode

# quote quotes unicode|bytes string into valid "..." unicode|bytes string always quoted with ".
def quote(s):
    s, wasunicode = _bstr(s)
    qs = _quote(s)
    if wasunicode:
        qs = qs.decode('UTF-8')
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
            elif unicodedata.category(r)[0] in _printable_cat0:
                emit(s[i:isize])

            # everything else goes in numeric byte escapes
            else:
                for j in xrange(i, isize):
                    emit(br'\x%02x' % ord(s[j:j+1]))

            i = isize

    return b'"' + b''.join(outv) + b'"'


_printable_cat0 = frozenset(['L', 'N', 'P', 'S'])   # letters, numbers, punctuation, symbols

_rune_error = u'\uFFFD' # unicode replacement character

# _utf8_decode_rune decodes next UTF8-character from byte string s.
#
# _utf8_decode_rune(s) -> (r, size)
def _utf8_decode_rune(s):
    assert isinstance(s, bytes)

    if len(s) == 0:
        return '', 0

    l = min(len(s), 4)  # max size of an UTF-8 encoded character
    while l > 0:
        try:
            r = s[:l].decode('utf-8', 'strict')
        except UnicodeDecodeError:
            l -= 1
            continue

        if len(r) == 1:
            return r, l

        l -= 1
        continue

    # invalid UTF-8
    return _rune_error, 1
