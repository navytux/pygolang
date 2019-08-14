# cython: language_level=2
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
"""Package golang.pyx provides Go-like features for Cython and runtime for golang.py

Channels
--------

Python-level channels, represented by pychan + pyselect

Cython-level channels, represented by chan[T] + select do not depend on Python
runtime and can be used in nogil code.

XXX

from golang cimport chan, select, XXX


Panic + recover
---------------

XXX
"""

# redirect `cimport golang` -> `cimport golang._golang`
#
# we do this because we cannot put pyx code into __init__.pyx - else Python and
# other tools (e.g. setuptools) fail to recognize golang/ as Python package.
from golang._golang cimport *
