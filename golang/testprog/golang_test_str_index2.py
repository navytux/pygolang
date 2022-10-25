#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2022  Nexedi SA and Contributors.
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
"""This program helps to verify [:] handling for bstr and ustr.

It complements golang_str_test.test_strings_index2.

It needs to verify [:] only lightly because thorough verification is done in
test_string_index, and here we need to verify only that __getslice__, inherited
from builtin str/unicode, does not get into our way.
"""

from __future__ import print_function, absolute_import

from golang import b, u


def main():
    us = u("миру мир")
    bs = b("миру мир")

    def emit(what, uobj, bobj):
        print("u"+what, repr(uobj))
        print("b"+what, repr(bobj))

    emit("s",       us,        bs)
    emit("s[:]",    us[:],     bs[:])
    emit("s[0:1]",  us[0:1],   bs[0:1])
    emit("s[0:2]",  us[0:2],   bs[0:2])
    emit("s[1:2]",  us[1:2],   bs[1:2])
    emit("s[0:-1]", us[0:-1],  bs[0:-1])


if __name__ == '__main__':
    main()
