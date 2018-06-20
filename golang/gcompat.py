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
"""Package gcompat provides Go-compatibility layer for Python"""

# qq is substitute for %q, which is missing in python.
#
# (python's automatic escape uses smartquotes quoting with either ' or ").
def qq(obj):
    # go: like %s, %q automatically converts to string
    if not isinstance(obj, basestring):
        obj = str(obj)
    return _quote(obj)

# _quote quotes string into valid "..." string always quoted with ".
def _quote(s):
    # TODO also accept unicode as input.
    # TODO output printable UTF-8 characters as-is, but escape non-printable UTF-8 and invalid UTF-8 bytes.
    outv = []
    # we don't want ' to be escaped
    for _ in s.split("'"):
        # this escape almost everything except " character
        # NOTE string_escape does not do smartquotes and always uses ' for quoting
        # (repr(str) is the same except it does smartquoting picking ' or " automatically)
        q = _.encode("string_escape")
        q = q.replace('"', r'\"')
        outv.append(q)
    return '"' + "'".join(outv) + '"'
