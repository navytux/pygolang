# -*- coding: utf-8 -*-
# Copyright (C) 2024-2026  Nexedi SA and Contributors.
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
"""Module _golang_early_test is preimported by golang before importing anything
else and before runtime patches to python runtime are applied.

It is used in tests that verify correctness of runtime patching wrt e.g. str
subclasses that are created by python stdlib very early. For example enum
module, that is preimported by re and many others, defines such subclasses.

See test_strings_early_str_subclass in golang_str_test.py for details.
"""

from __future__ import print_function, absolute_import

class Str(str):
    __slots__ = ()


class Init(object):
    __slots__ = ()
    value = None    # not slot to avoid 'multiple bases have instance lay-out conflict'
    def __init__(self, v):
        Init.value = v

class Str_Init(str, Init):
    __slots__ = ()

class Init_Str(Init, str):
    __slots__ = ()


# enum overrides __new__ with custom code.
class Str_New(str):
    __slots__ = ()
    def __new__(cls, x):
        return x


# diamond case that needs toposort to be handled properly.
class Diamond(Str, Str_Init):
    __slots__ = ()
