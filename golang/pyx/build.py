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
"""XXX"""   # XXX

import setuptools_dso

import pkgutil
from distutils.errors import DistutilsError
class BuildError(DistutilsError):
    pass
from os.path import dirname

# _PyPkg provides information about 1 py package.
class _PyPkg:
    # .name - full package name, e.g. golang.time
    # .path - filesystem path of the package
    #         (file for module, directory for pkg/__init__.py)
    pass

# _pyimport returns path to specified package.
# e.g. _pyimport("golang") -> /path/to/pygolang/golang  XXX -> _PyPkg
# XXX error -> what?
def _pyimport(pkgname): # -> _PyPkg
    pkg = pkgutil.get_loader(pkgname)
    # XXX can also raise ImportError for pkgname with '.' inside
    if pkg is None: # package not found
        raise BuildError("package %r not found" % (pkgname,))
    path = pkg.get_filename()
    if path.endswith("__init__.py"):
        path = dirname(path) # .../pygolang/golang/__init__.py -> .../pygolang/golang
    pypkg = _PyPkg()
    pypkg.name = pkgname
    pypkg.path = path
    return pypkg

# XXX
def Extension(name, sources, *argv, **kw):
    gopkg = _pyimport("golang")
    pygo  = dirname(gopkg.path) # .../pygolang/golang -> .../pygolang

    # XXX include_dirs += [pygo]
    # XXX dsos += ['golang.runtime.libgolang'],
    # XXX language = 'c++'
    ...

    return setuptools_dso.Extension(name, sources, *argv, **kw)
