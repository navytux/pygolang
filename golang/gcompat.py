# -*- coding: utf-8 -*-
# Copyright (C) 2018-2019  Nexedi SA and Contributors.
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
"""Package gcompat provides Go-compatibility layer for Python"""

from __future__ import print_function, absolute_import

from golang import strconv
import six

# qq is substitute for %q, which is missing in python.
#
# (python's automatic escape uses smartquotes quoting with either ' or ").
#
# like %s, %q automatically converts its argument to string.
def qq(obj):
    # make sure obj is text | bytes
    # py2: unicode | str
    # py3: str     | bytes
    if not isinstance(obj, (six.text_type, six.binary_type)):
        obj = str(obj)

    qobj = strconv.quote(obj)

    # `printf('%s', qq(obj))` should work. For this make sure qobj is always a
    # str - not bytes under py3 (if it was bytes it will print e.g. as b'...')
    if six.PY3 and isinstance(qobj, bytes):
        qobj = qobj.decode('UTF-8')

    return qobj
