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
"""Package build provides infrastructure to build Cython Pygolang-based packages.

Use `setup` and `Extension` to build packages. For example::

    from golang.pyx.build import setup, Extension

    setup(
        name        = 'mypkg',
        description = 'my Pygolang/Cython-based package',
        ...
        ext_modules = [Extension('mypkg.mymod', ['mypkg/mymod.pyx'])],
    )
"""

from __future__ import print_function, absolute_import

# pygolang uses setuptools_dso.DSO to build libgolang; all extensions link to it.
import setuptools_dso

import sys, pkgutil, platform, sysconfig
from os.path import dirname, join, exists
from distutils.errors import DistutilsError

# Error represents a build error.
class Error(DistutilsError):
    pass

# _PyPkg provides information about 1 py package.
class _PyPkg:
    # .name - full package name, e.g. "golang.time"
    # .path - filesystem path of the package
    #         (file for module, directory for pkg/__init__.py)
    pass

# _findpkg finds specified python package and returns information about it.
#
# e.g. _findpkg("golang") -> _PyPkg("/path/to/pygolang/golang")
def _findpkg(pkgname):  # -> _PyPkg
    pkg = pkgutil.get_loader(pkgname)
    if pkg is None: # package not found
        raise Error("package %r not found" % (pkgname,))
    path = pkg.get_filename()
    if path.endswith("__init__.py"):
        path = dirname(path) # .../pygolang/golang/__init__.py -> .../pygolang/golang
    pypkg = _PyPkg()
    pypkg.name = pkgname
    pypkg.path = path
    return pypkg


# _build_ext amends setuptools_dso.build_ext to allow combining C and C++
# sources in one extension without hitting `error: invalid argument
# '-std=c++11' not allowed with 'C'`.
_dso_build_ext = setuptools_dso.build_ext
class _build_ext(_dso_build_ext):
    def build_extension(self, ext):
        # wrap _compiler <src> -> <obj> with our code
        _compile = self.compiler._compile
        def _(obj, src, ext, cc_args, extra_postargs, pp_opts):
            # filter_out removes arguments that start with argprefix
            cc_args         = cc_args[:]
            extra_postargs  = extra_postargs[:]
            pp_opts         = pp_opts[:]
            def filter_out(argprefix):
                for l in (cc_args, extra_postargs, pp_opts):
                    _ = []
                    for arg in l:
                        if not arg.startswith(argprefix):
                            _.append(arg)
                    l[:] = _

            # filter-out C++ only options from non-C++ sources
            #
            # reason: while gcc only warns about -std=c++ passed with C source,
            # clang considers that an error. Given that with distutils /
            # setuptools the _same_ compiler is used to compile C and C++
            # sources, and that it is not possible to provide per-source flags,
            # without filtering, that leads to inability to use both C and C++
            # sources in one extension.
            cxx = (self.compiler.language_map[ext] == 'c++')
            if not cxx:
                filter_out('-std=c++')
                filter_out('-std=gnu++')

            _compile(obj, src, ext, cc_args, extra_postargs, pp_opts)
        self.compiler._compile = _
        try:
            _dso_build_ext.build_extension(self, ext) # super doesn't work for _dso_build_ext
        finally:
            self.compiler._compile = _compile


# setup should be used instead of setuptools.setup
def setup(**kw):
    # setuptools_dso.setup hardcodes setuptools_dso.build_ext to be used.
    # temporarily inject our code there.
    _ = setuptools_dso.build_ext
    try:
        setuptools_dso.build_ext = _build_ext
        setuptools_dso.setup(**kw)
    finally:
        setuptools_dso.build_ext = _

# Extension should be used to build extensions that use pygolang.
#
# For example:
#
#   setup(
#       ...
#       ext_modules = [Extension('mypkg.mymod', ['mypkg/mymod.pyx'])],
#   )
def Extension(name, sources, **kw):
    # find pygolang root
    gopkg = _findpkg("golang")
    pygo  = dirname(gopkg.path) # .../pygolang/golang -> .../pygolang
    if pygo == '':
        pygo = '.'

    kw = kw.copy()

    # prepend -I<pygolang> so that e.g. golang/libgolang.h is found
    incv = kw.get('include_dirs', [])[:]
    incv.insert(0, pygo)
    kw['include_dirs'] = incv

    # link with libgolang.so
    dsov = kw.get('dsos', [])[:]
    dsov.insert(0, 'golang.runtime.libgolang')
    kw['dsos'] = dsov

    # default language to C++ (chan[T] & co are accessible only via C++)
    lang = kw.setdefault('language', 'c++')

    # default to C++11 (chan[T] & co require C++11 features)
    if lang == 'c++':
        ccextra = kw.get('extra_compile_args', [])[:]
        ccextra.insert(0, '-std=c++11') # if another -std=... was already there - it will override us
        kw['extra_compile_args'] = ccextra

    # some depends to workaround a bit lack of proper dependency tracking in
    # setuptools/distutils.
    dependv = kw.get('depends', [])[:]
    dependv.append('%s/golang/libgolang.h'  % pygo)
    dependv.append('%s/golang/_golang.pxd'  % pygo)
    dependv.append('%s/golang/__init__.pxd' % pygo)
    kw['depends'] = dependv

    # workaround pip bug that for virtualenv case headers are installed into
    # not-searched include path. https://github.com/pypa/pip/issues/4610
    # (without this e.g. "greenlet/greenlet.h" is not found)
    venv_inc = join(sys.prefix, 'include', 'site', 'python' + sysconfig.get_python_version())
    if exists(venv_inc):
        kw['include_dirs'].append(venv_inc)

    # provide POSIX/PYPY/... defines to Cython
    POSIX = ('posix' in sys.builtin_module_names)
    PYPY  = (platform.python_implementation() == 'PyPy')
    pyxenv = kw.get('cython_compile_time_env', {})
    pyxenv.setdefault('POSIX',  POSIX)
    pyxenv.setdefault('PYPY',   PYPY)
    kw['cython_compile_time_env'] = pyxenv

    # XXX hack, because setuptools_dso.Extension is not Cython.Extension
    # del from kw to avoid "Unknown Extension options: 'cython_compile_time_env'"
    #ext = setuptools_dso.Extension(name, sources, **kw)
    pyxenv = kw.pop('cython_compile_time_env')
    ext = setuptools_dso.Extension(name, sources, **kw)
    ext.cython_compile_time_env = pyxenv

    return ext
