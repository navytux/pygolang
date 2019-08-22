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
"""Demo package that links to and uses golang in pyx mode."""

from __future__ import print_function

from setuptools_dso import Extension, setup


import pkgutil
from distutils.errors import DistutilsError
class BuildError(DistutilsError):
    pass
from os.path import dirname

# find_pkg returns path to specified package.
# e.g. find_pkg("golang") -> /path/to/pygolang/golang
# XXX error -> what?
def find_pkg(pkgname):
    pkg = pkgutil.get_loader(pkgname)
    # XXX can also raise ImportError for pkgname with '.' inside
    if pkg is None: # package not found
        raise BuildError("package %r not found" % (pkgname,))
    path = pkg.get_filename()
    if path.endswith("__init__.py"):
        path = dirname(path) # .../pygolang/golang/__init__.py -> .../pygolang/golang
    return path

golang = find_pkg("golang")
import sys
print(file=sys.stderr)
print('golang: %r' % golang, file=sys.stderr)
groot = dirname(golang)
print('groot:  %r' % groot, file=sys.stderr)
#1/0

# XXX ^^^ -> golang.pyx.build .cimport()  XXX or .import() ?

setup(
    name        = 'golang_pyx_user',
    description = 'test project that uses pygolang in pyx mode',

    ext_modules = [Extension('pyxuser.test', ['pyxuser/test.pyx'],
                   include_dirs=[groot],
                   dsos    = ['golang.runtime.libgolang'],
                   language='c++')],
)
