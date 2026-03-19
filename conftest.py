# pygolang | pytest config
# Copyright (C) 2021-2025  Nexedi SA and Contributors.
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

import gc


# Do full GC before pytest exits, to avoid false positives in the leak detector.
def pytest_unconfigure():
    gc.collect()


# ignore tests in 3rdparty/ - else it breaks as e.g.
#
# 3rdparty/capstone/bindings/python/test_all.py:3: in <module>
#     import test_basic, test_arm, test_arm64, test_detail, test_lite, test_m68k, test_mips, \
# 3rdparty/capstone/bindings/python/test_basic.py:5: in <module>
#     from capstone import *
# 3rdparty/capstone/bindings/python/capstone/__init__.py:428: in <module>
#     raise ImportError("ERROR: fail to load the dynamic library.")
# E   ImportError: ERROR: fail to load the dynamic library.
collect_ignore = ["3rdparty"]
