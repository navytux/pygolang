#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2022-2023  Nexedi SA and Contributors.
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
"""This program helps to verify b, u and underlying bstr and ustr.

It complements golang_str_test.test_strings_print.
"""

from __future__ import print_function, absolute_import

from golang import b, u
from golang.gcompat import qq

def main():
    sb = b("привет αβγ b")
    su = u("привет αβγ u")
    print("print(b):", sb)
    print("print(u):", su)
    print("print(qq(b)):", qq(sb))
    print("print(qq(u)):", qq(su))
    print("print(repr(b)):", repr(sb))
    print("print(repr(u)):", repr(su))

    # py2: print(dict) calls PyObject_Print(flags=0) for both keys and values,
    #      not with flags=Py_PRINT_RAW used by default almost everywhere else.
    #      this way we can verify whether bstr.tp_print handles flags correctly.
    print("print({b: u}):", {sb: su})


if __name__ == '__main__':
    main()
