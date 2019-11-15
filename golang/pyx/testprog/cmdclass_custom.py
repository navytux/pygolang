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
"""cmdclass_custom.py helps tests to verify that e.g. custom build_ext can be used"""

from __future__ import print_function, absolute_import

from golang.pyx.build import setup, build_ext

class mybuild_ext(build_ext):
    def run(self):
        print('pyx.build:RUN_BUILD_EXT')
        # just print - _not_ recursing into build_ext.run

setup(
    cmdclass    = {'build_ext': mybuild_ext},
)
