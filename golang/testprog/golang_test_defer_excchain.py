#!/usr/bin/env python
# Copyright (C) 2019  Nexedi SA and Contributors.
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
"""This program is used to test traceback dump of chained exceptions.

When run it fails and Python should print the dump.
The dump is verified by test driver against golang_test_defer_excchain.txt .
"""

from __future__ import print_function, absolute_import

from golang import defer, func

def d1():
    raise RuntimeError("d1: aaa")
def d2():
    1/0
def d3():
    raise RuntimeError("d3: bbb")

@func
def main():
    defer(d3)
    defer(d2)
    defer(d1)
    raise RuntimeError("err")

if __name__ == "__main__":
    main()
