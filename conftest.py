# pygolang | pytest config
# Copyright (C) 2021-2024  Nexedi SA and Contributors.
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


# ignore tests in distorm - else it breaks as e.g.
#
# 3rdparty/funchook/distorm/python/test_distorm3.py:15: in <module>
#     import distorm3
# 3rdparty/funchook/distorm/python/distorm3/__init__.py:57: in <module>
#     _distorm = _load_distorm()
# 3rdparty/funchook/distorm/python/distorm3/__init__.py:55: in _load_distorm
#     raise ImportError("Error loading the diStorm dynamic library (or cannot load library into process).")
# E   ImportError: Error loading the diStorm dynamic library (or cannot load library into process).
collect_ignore = ["3rdparty"]
