# -*- coding: utf-8 -*-
# pygolang | pythonic package setup
# Copyright (C) 2018-2024  Nexedi SA and Contributors.
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

# patch cython to allow `cdef class X(bytes)` while building pygolang to
# workaround https://github.com/cython/cython/issues/711
# see `cdef class pybstr` in golang/_golang_str.pyx for details.
# (should become unneeded with cython 3 once https://github.com/cython/cython/pull/5212 is finished)
import inspect
from Cython.Compiler.PyrexTypes import BuiltinObjectType
def pygo_cy_builtin_type_name_set(self, v):
    self._pygo_name = v
def pygo_cy_builtin_type_name_get(self):
    name = self._pygo_name
    if name == 'bytes':
        caller = inspect.currentframe().f_back.f_code.co_name
        if caller == 'analyse_declarations':
            # need anything different from 'bytes' to deactivate check in
            # https://github.com/cython/cython/blob/c21b39d4/Cython/Compiler/Nodes.py#L4759-L4762
            name = 'xxx'
    return name
BuiltinObjectType.name = property(pygo_cy_builtin_type_name_get, pygo_cy_builtin_type_name_set)

from setuptools import find_packages
from setuptools.command.install_scripts import install_scripts as _install_scripts
from setuptools.command.develop import develop as _develop
from distutils import sysconfig
from os.path import dirname, join
import sys, os, re

# read file content
def readfile(path): # -> str
    with open(path, 'rb') as f:
        data = f.read()
        if not isinstance(data, str):   # py3
            data = data.decode('utf-8')
        return data

# reuse golang.pyx.build to build pygolang dso and extensions.
# we have to be careful and inject synthetic golang package in order to be
# able to import golang.pyx.build without built/working golang.
trun = {}
exec(readfile('trun'), trun)
trun['ximport_empty_golangmod']()
from golang.pyx.build import setup, DSO, Extension as Ext


# grep searches text for pattern.
# return re.Match object or raises if pattern was not found.
def grep1(pattern, text):
    rex = re.compile(pattern, re.MULTILINE)
    m = rex.search(text)
    if m is None:
        raise RuntimeError('%r not found' % pattern)
    return m

# find our version
_ = readfile(join(dirname(__file__), 'golang/__init__.py'))
_ = grep1('^__version__ = "(.*)"$', _)
version = _.group(1)

# XInstallGPython customly installs bin/gpython.
#
# console_scripts generated by setuptools do lots of imports. However we need
# gevent.monkey.patch_all() to be done first - before all other imports. We
# could use plain scripts for gpython, however even for plain scripts
# setuptools wants to inject pkg_resources import for develop install, and
# pkg_resources does import lots of modules.
#
# -> generate the script via our custom install, but keep gpython listed as
# console_scripts entry point, so that pip knows to remove the file on develop
# uninstall.
#
# NOTE in some cases (see below e.g. about bdist_wheel) we accept for gpython
# to be generated not via XInstallGPython - because in those cases pkg_resources
# and entry points are not used - just plain `import gpython`.
class XInstallGPython:
    gpython_installed = 0

    # NOTE cannot override write_script, because base class - _install_scripts
    # or _develop, is old-style and super does not work with it.
    #def write_script(self, script_name, script, mode="t", blockers=()):
    #    script_name, script = self.transform_script(script_name, script)
    #    super(XInstallGPython, self).write_script(script_name, script, mode, blockers)

    # transform_script transform to-be installed script to override installed gpython content.
    #
    # (script_name, script) -> (script_name, script)
    def transform_script(self, script_name, script):
        # on windows setuptools installs 3 files:
        #   gpython-script.py
        #   gpython.exe
        #   gpython.exe.manifest
        # we want to override .py only.
        #
        # for-windows build could be cross - e.g. from linux via bdist_wininst -
        # -> we can't rely on os.name. Rely on just script name.
        if script_name in ('gpython', 'gpython-script.py'):
            script  = '#!%s\n' % sys.executable
            script += '\nfrom gpython import main; main()\n'
            self.gpython_installed += 1

        return script_name, script


# install_scripts is custom scripts installer that takes gpython into account.
class install_scripts(XInstallGPython, _install_scripts):
    def write_script(self, script_name, script, mode="t", blockers=()):
        script_name, script = self.transform_script(script_name, script)
        _install_scripts.write_script(self, script_name, script, mode, blockers)

    def run(self):
        _install_scripts.run(self)
        # bdist_wheel disables generation of scripts for entry-points[1]
        # and pip/setuptools regenerate them when installing the wheel[2].
        #
        #   [1] https://github.com/pypa/wheel/commit/0d7f398b
        #   [2] https://github.com/pypa/wheel/commit/9aaa6628
        #
        # since setup.py is not included into the wheel, we cannot control
        # entry-point installation when the wheel is installed. However,
        # console script generated when installing the wheel looks like:
        #
        #   #!/path/to/python
        #   # -*- coding: utf-8 -*-
        #   import re
        #   import sys
        #
        #   from gpython import main
        #
        #   if __name__ == '__main__':
        #       sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
        #       sys.exit(main())
        #
        # which does not import pkg_resources. Since we also double-check in
        # gpython itself that pkg_resources and other modules are not imported,
        # we are ok with this.
        if not self.no_ep:
            # regular install
            assert self.gpython_installed == 1
        else:
            # bdist_wheel
            assert self.gpython_installed == 0
            assert len(self.outfiles) == 0


# develop, similarly to install_scripts, is used to handle gpython in `pip install -e` mode.
class develop(XInstallGPython, _develop):
    def write_script(self, script_name, script, mode="t", blockers=()):
        script_name, script = self.transform_script(script_name, script)
        _develop.write_script(self, script_name, script, mode, blockers)

    def install_egg_scripts(self, dist):
        _develop.install_egg_scripts(self, dist)
        assert self.gpython_installed == 1


# requirements of packages under "golang." namespace
R = {
    'cmd.pybench':      {'pytest', 'py ; python_version >= "3"'},
    'pyx.build':        {'setuptools', 'wheel', 'cython < 3', 'setuptools_dso >= 2.8'},
    'x.perf.benchlib':  {'numpy'},
}
# TODO generate `a.b -> a`, e.g. x.perf = join(x.perf.*); x = join(x.*)
Rall = set()
for pkg in R:
    Rall.update(R[pkg])
R['all'] = Rall

# ipython/pytest are required to test py2 integration patches
# zodbpickle is used to test pickle support for bstr/ustr
R['all_test'] = Rall.union(['ipython', 'pytest', 'zodbpickle']) # pip does not like "+" in all+test

# extras_require <- R
extras_require = {}
for k in sorted(R.keys()):
    extras_require[k] = list(sorted(R[k]))


# get_python_libdir() returns path where libpython is located
def get_python_libdir():
    # mimic what distutils.command.build_ext does
    if os.name == 'nt':
        return join(sysconfig.get_config_var('installed_platbase'), 'libs')
    else:
        return sysconfig.get_config_var('LIBDIR')

setup(
    name        = 'pygolang',
    version     = version,
    description = 'Go-like features for Python and Cython',
    long_description = '%s\n----\n\n%s' % (
                            readfile('README.rst'), readfile('CHANGELOG.rst')),
    long_description_content_type  = 'text/x-rst',
    url         = 'https://pygolang.nexedi.com',
    project_urls= {
        'Bug Tracker':   'https://lab.nexedi.com/nexedi/pygolang/issues',
        'Source Code':   'https://lab.nexedi.com/nexedi/pygolang',
        'Documentation': 'https://pypi.org/project/pygolang',
    },
    license     = 'GPLv3+ with wide exception for Open-Source',
    author      = 'Kirill Smelkov',
    author_email= 'kirr@nexedi.com',

    keywords    = 'golang go channel goroutine concurrency GOPATH python import gpython gevent cython nogil GIL',

    packages    = find_packages(),

    x_dsos      = [DSO('golang.runtime.libgolang',
                        ['golang/runtime/libgolang.cpp',
                         'golang/runtime/internal/atomic.cpp',
                         'golang/runtime/internal/syscall.cpp',
                         'golang/context.cpp',
                         'golang/errors.cpp',
                         'golang/fmt.cpp',
                         'golang/io.cpp',
                         'golang/os.cpp',
                         'golang/os/signal.cpp',
                         'golang/strings.cpp',
                         'golang/sync.cpp',
                         'golang/time.cpp'],
                        depends = [
                            'golang/libgolang.h',
                            'golang/runtime/internal.h',
                            'golang/runtime/internal/atomic.h',
                            'golang/runtime/internal/syscall.h',
                            'golang/runtime/platform.h',
                            'golang/context.h',
                            'golang/cxx.h',
                            'golang/errors.h',
                            'golang/fmt.h',
                            'golang/io.h',
                            'golang/os.h',
                            'golang/os/signal.h',
                            'golang/strings.h',
                            'golang/sync.h',
                            'golang/time.h',
                            '3rdparty/ratas/src/timer-wheel.h'],
                        include_dirs    = [
                            '3rdparty/include',
                            '3rdparty/ratas/src'],
                        define_macros   = [('BUILDING_LIBGOLANG', None)],
                        soversion       = '0.1'),

                    DSO('golang.runtime.libpyxruntime',
                        ['golang/runtime/libpyxruntime.cpp'],
                        depends = ['golang/pyx/runtime.h'],
                        include_dirs    = [sysconfig.get_python_inc()],
                        library_dirs    = [get_python_libdir()],
                        define_macros   = [('BUILDING_LIBPYXRUNTIME', None)],
                        soversion       = '0.1')],

    ext_modules = [
                    Ext('golang._golang',
                        ['golang/_golang.pyx'],
                        depends = [
                            'golang/_golang_str.pyx',
                            'golang/_golang_str_pickle.pyx']),

                    Ext('golang.runtime._runtime_thread',
                        ['golang/runtime/_runtime_thread.pyx']),

                    Ext('golang.runtime._runtime_gevent',
                        ['golang/runtime/_runtime_gevent.pyx']),

                    Ext('golang.pyx.runtime',
                        ['golang/pyx/runtime.pyx'],
                        dsos = ['golang.runtime.libpyxruntime']),

                    Ext('golang._golang_test',
                        ['golang/_golang_test.pyx',
                         'golang/runtime/libgolang_test_c.c',
                         'golang/runtime/libgolang_test.cpp']),

                    Ext('golang.pyx._runtime_test',
                        ['golang/pyx/_runtime_test.pyx'],
                        dsos = ['golang.runtime.libpyxruntime']),

                    Ext('golang._context',
                        ['golang/_context.pyx']),

                    Ext('golang._cxx_test',
                        ['golang/_cxx_test.pyx',
                         'golang/cxx_test.cpp']),

                    Ext('golang._errors',
                        ['golang/_errors.pyx']),
                    Ext('golang._errors_test',
                        ['golang/_errors_test.pyx',
                         'golang/errors_test.cpp']),

                    Ext('golang._fmt',
                        ['golang/_fmt.pyx']),
                    Ext('golang._fmt_test',
                        ['golang/_fmt_test.pyx',
                         'golang/fmt_test.cpp']),

                    Ext('golang._io',
                        ['golang/_io.pyx']),

                    Ext('golang._os',
                        ['golang/_os.pyx']),
                    Ext('golang._os_test',
                        ['golang/_os_test.pyx',
                         'golang/os_test.cpp']),

                    Ext('golang.os._signal',
                        ['golang/os/_signal.pyx']),

                    Ext('golang._strconv',
                        ['golang/_strconv.pyx']),

                    Ext('golang._strings_test',
                        ['golang/_strings_test.pyx',
                         'golang/strings_test.cpp']),

                    Ext('golang._sync',
                        ['golang/_sync.pyx'],
                        dsos = ['golang.runtime.libpyxruntime'],
                        define_macros = [('_LIBGOLANG_SYNC_INTERNAL_API', None)]),
                    Ext('golang._sync_test',
                        ['golang/_sync_test.pyx',
                         'golang/sync_test.cpp']),

                    Ext('golang._time',
                        ['golang/_time.pyx'],
                        dsos = ['golang.runtime.libpyxruntime']),
                  ],
    include_package_data = True,

    install_requires = ['gevent', 'six', 'decorator', 'Importing;python_version<="2.7"',
                        # only runtime part: for dylink_prepare_dso
                        # also need to pin setuptools ≥ 60.2 because else wheel configures logging
                        # to go to stdout and so dylink_prepare_dso garbles program output
                        'setuptools_dso >= 2.8',
                        'setuptools >= 60.2 ; python_version>="3"',
                        # pyx.build -> setuptools_dso uses multiprocessing
                        # setuptools_dso uses multiprocessing only on Python3, and only on systems where
                        # mp.get_start_method()!='fork', while geventmp does not work on windows.
                        'geventmp ; python_version>="3" and platform_system != "Windows" ',
                       ],
    extras_require   = extras_require,

    entry_points= {'console_scripts': [
                        # NOTE gpython is handled specially - see XInstallGPython.
                        'gpython  = gpython:main',

                        'py.bench = golang.cmd.pybench:main',
                      ]
                  },

    cmdclass    = {
        'install_scripts':  install_scripts,
        'develop':          develop,
    },

    classifiers = [_.strip() for _ in """\
        Development Status :: 4 - Beta
        Intended Audience :: Developers
        Programming Language :: Python
        Programming Language :: Cython
        Programming Language :: Python :: 2
        Programming Language :: Python :: 2.7
        Programming Language :: Python :: 3
        Programming Language :: Python :: 3.8
        Programming Language :: Python :: 3.9
        Programming Language :: Python :: 3.10
        Programming Language :: Python :: 3.11
        Programming Language :: Python :: 3.12
        Programming Language :: Python :: Implementation :: CPython
        Programming Language :: Python :: Implementation :: PyPy
        Operating System :: POSIX
        Operating System :: POSIX :: Linux
        Operating System :: Unix
        Operating System :: MacOS
        Operating System :: Microsoft :: Windows
        Topic :: Software Development :: Interpreters
        Topic :: Software Development :: Libraries :: Python Modules\
    """.splitlines()]
)
