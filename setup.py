# pygolang | pythonic package setup
# Copyright (C) 2018-2019  Nexedi SA and Contributors.
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

from setuptools import find_packages
# setuptools has Library but this days it is not well supported and test for it
# has been killed https://github.com/pypa/setuptools/commit/654c26f78a30
# -> use setuptools_dso instead.
from setuptools_dso import DSO
from setuptools.command.install_scripts import install_scripts as _install_scripts
from setuptools.command.develop import develop as _develop
#import sysconfig, platform
from os.path import dirname, join   #, exists
import sys, re

# reuse golang.pyx.build to build pygolang extensions.
# we have to be careful and inject synthethic golang package in order to be
# able to import golang.pyx.build without built golang.
import imp
golang = sys.modules['golang'] = imp.new_module('golang')
golang.__package__ = 'golang'
golang.__path__    = ['golang']
golang.__file__    = 'golang/__init__.py'
from golang.pyx.build import setup, Extension as Ext

# read file content
def readfile(path):
    with open(path, 'r') as f:
        return f.read()

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


"""
# Ext creates Extension with common settings.
def Ext(name, srcv, **kw):
    # prepend -I<top> so that e.g. golang/libgolang.h is found
    incv = kw.get('include_dirs', [])
    incv.insert(0, '.')

    # workaround pip bug that for virtualenv case headers are installed into
    # not-searched include path. https://github.com/pypa/pip/issues/4610
    # (without this e.g. "greenlet/greenlet.h" is not found)
    venv_inc = join(sys.prefix, 'include', 'site', 'python' + sysconfig.get_python_version())
    if exists(venv_inc):
        incv.append(venv_inc)

    # provide POSIX/PYPY/... defines to Cython      XXX -> golang.pyx.build
    POSIX = ('posix' in sys.builtin_module_names)
    PYPY  = (platform.python_implementation() == 'PyPy')
    pyxenv = kw.get('cython_compile_time_env', {})
    pyxenv.setdefault('POSIX',  POSIX)
    pyxenv.setdefault('PYPY',   PYPY)
    kw['cython_compile_time_env'] = pyxenv

    kw['include_dirs'] = incv
    #return Extension(name, srcv, **kw)
    # XXX hack, because Extension is not Cython.Extension, but setuptools_dso.Extension
    # del from kw to avoid "Unknown Extension options: 'cython_compile_time_env'"
    pyxenv = kw.pop('cython_compile_time_env')
    ext = Extension(name, srcv, **kw)
    ext.cython_compile_time_env = pyxenv
    return ext
"""

# XXX extra require
#   cmd/pybench         pytest
#   pyx/build           cython, setuptools_dso >= 1.2
#   x/perf/benchlib     numpy
#   ...
#   + generate e.g. pyx = join(pyx/*)
#   all = join ^^^
# XXX find_packages -> init as empty?

setup(
    name        = 'pygolang',
    version     = version,
    description = 'Go-like features for Python and Cython',
    long_description = '%s\n----\n\n%s' % (
                            readfile('README.rst'), readfile('CHANGELOG.rst')),
    long_description_content_type  = 'text/x-rst',
    url         = 'https://lab.nexedi.com/kirr/pygolang',
    project_urls= {
        'Bug Tracker':   'https://lab.nexedi.com/kirr/pygolang/issues',
        'Source Code':   'https://lab.nexedi.com/kirr/pygolang',
        'Documentation': 'https://pypi.org/project/pygolang',
    },
    license     = 'GPLv3+ with wide exception for Open-Source',
    #   license_file= 'COPYING',        XXX gives warning "unknown distro option"
    author      = 'Kirill Smelkov',
    author_email= 'kirr@nexedi.com',

    # XXX + stackless
    keywords    = 'golang go channel goroutine concurrency GOPATH python import gpython gevent',

    packages    = find_packages(),

    # XXX don't install headers - use them directly from installed package
    #headers     = ['golang/libgolang.h'],

    x_dsos      = [DSO('golang.runtime.libgolang', ['golang/runtime/libgolang.cpp'],
                        depends         = ['golang/libgolang.h'],
                        include_dirs    = ['.', '3rdparty/include'],
                        define_macros   = [('BUILDING_LIBGOLANG', None)],
                        soversion       = '0.1')],  # XXX take soversion from version?
    ext_modules = [
                    Ext('golang._golang',
                        ['golang/_golang.pyx']),

                    Ext('golang.runtime._runtime_thread',
                        ['golang/runtime/_runtime_thread.pyx'],
                        language = "c"),

                    Ext('golang.runtime._runtime_gevent',
                        ['golang/runtime/_runtime_gevent.pyx'],
                        language = 'c'),

                    Ext('golang._golang_test',
                        ['golang/_golang_test.pyx',
                         'golang/runtime/libgolang_test_c.c',
                         'golang/runtime/libgolang_test.cpp']),

                    Ext('golang._time',
                        ['golang/_time.pyx']),

                    Ext('golang._internal',
                        ['golang/_internal.pyx'],
                        language = 'c'),
                  ],
    platforms   = 'any',
    include_package_data = True,

    install_requires = ['gevent', 'six', 'decorator'],

    extras_require = {
                  'test': ['pytest',
                           'numpy',    # XXX numpy for t(benchlib)

                           # for testprog/golang_pyx_user/
                           # XXX move -> pygolang[build] ?
                           'cython',
                           'setuptools_dso',
                          ],
    },

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

    # XXX + stackless
    classifiers = [_.strip() for _ in """\
        Development Status :: 3 - Alpha
        Intended Audience :: Developers

        XXX License
        Operating System :: OS Independent
        Operating System :: POSIX
        Operating System :: Unix
        Operating System :: Microsoft :: Windows

        Programming Language :: Python
        Programming Language :: Python :: 2
        Programming Language :: Python :: 2.7
        Programming Language :: Python :: 3
        Programming Language :: Python :: 3.5
        Programming Language :: Python :: 3.6
        Programming Language :: Python :: 3.7
        Programming Language :: Python :: Implementation :: CPython
        Programming Language :: Python :: Implementation :: PyPy
        Topic :: Software Development :: Interpreters
        Topic :: Software Development :: Libraries :: Python Modules\
    """.splitlines()]
)
