#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2018-2020  Nexedi SA and Contributors.
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
"""gpython ... - run python ... with gevent & golang activated.

gpython is substitute for standard python interpreter with the following
differences:

- gevent is pre-activated and stdlib is patched to be gevent aware;
- go, chan, select etc are put into builtin namespace;
- default string encoding is always set to UTF-8.

Gevent activation can be disabled via `-X gpython.runtime=threads`, or
$GPYTHON_RUNTIME=threads.
"""

# NOTE gpython is kept out of golang/ , since even just importing e.g. golang.cmd.gpython,
# would import golang, and we need to do gevent monkey-patching ASAP - before that.
#
# we also keep it in gpython/__init__.py instead of gpython.py, since the latter does not
# work correctly with `pip install` (gpython script is installed, but gpython module is not).

# NOTE don't import anything at global scope - we need gevent to be imported first.
from __future__ import print_function, absolute_import


# pymain mimics `python ...`
#
# argv is what comes via `...` without first [0] for python.
# init, if provided, is called after options are parsed, but before interpreter start.
def pymain(argv, init=None):
    import sys
    from os.path import dirname, realpath

    run = None          # function to run according to -c/-m/file/interactive
    version = False     # set if `-V`
    warnoptions = []    # collected `-W arg`

    while len(argv) > 0:
        # -V / --version
        if argv[0] in ('-V', '--version'):
            version = True
            break

        # -c command
        elif argv[0].startswith('-c'):
            cmd  = argv[0][2:] # -c<command> also works
            argv = argv[1:]
            if cmd == '':
                cmd  = argv[0]
                argv = argv[1:]
            sys.argv = ['-c'] + argv # python leaves '-c' as argv[0]
            sys.path.insert(0, '')   # cwd
            def run():
                import six
                # exec with the same globals `python -c ...` does
                g = {'__name__':    '__main__',
                     '__doc__':     None,
                     '__package__': None}
                six.exec_(cmd, g)
            break

        # -m module
        elif argv[0].startswith('-m'):
            mod  = argv[0][2:] # -m<module> also works
            argv = argv[1:]
            if mod == '':
                mod  = argv[0]
                argv = argv[1:]
            sys.argv = [mod] + argv
            # sys.path <- cwd
            # NOTE python2 injects '', while python3 injects realpath('')
            # we stick to python3 behaviour, as it is more sane because e.g.
            # import path does not change after chdir.
            sys.path.insert(0, realpath(''))  # realpath(cwd)
            def run():
                import runpy
                # search sys.path for module and run corresponding .py file as script
                runpy.run_module(mod, init_globals={'__doc__': None},
                                 run_name='__main__', alter_sys=True)
            break

        # -W arg  (warning control)
        elif argv[0].startswith('-W'):
            wopt = argv[0][2:] # -W<arg> also works
            argv = argv[1:]
            if wopt == '':
                wopt = argv[0]
                argv = argv[1:]
            warnoptions.append(wopt)

        elif argv[0].startswith('-'):
            print("unknown option: '%s'" % argv[0], file=sys.stderr)
            sys.exit(2)

        # file
        else:
            sys.argv = argv
            filepath = argv[0]

            sys.path.insert(0, realpath(dirname(filepath))) # not abspath -> see PySys_SetArgvEx
            def run():
                # exec with same globals `python file.py` does
                # XXX use runpy.run_path() instead?
                g = {'__name__':    '__main__',
                     '__file__':    filepath,
                     '__doc__':     None,
                     '__package__': None}
                _execfile(filepath, g)
            break

    # interactive console
    if run is None:
        sys.argv = ['']
        sys.path.insert(0, '')  # cwd

        def run():
            import code
            from six.moves import input as raw_input
            # like code.interact() but with overridden console.raw_input _and_
            # readline imported (code.interact mutually excludes those two).
            try:
                import readline # enable interactive editing
            except ImportError:
                pass

            console = code.InteractiveConsole()
            def _(prompt):
                # python behaviour: don't print '>>>' if stdin is not a tty
                # (builtin raw_input always prints prompt)
                if not sys.stdin.isatty():
                    prompt=''
                return raw_input(prompt)
            console.raw_input = _

            console.interact()


    # ---- options processed -> start the interpreter ----
    if init is not None:
        init()

    # handle -V/--version
    if version:
        ver = []
        if 'GPython' in sys.version:
            golang = sys.modules['golang'] # must be already imported
            gevent = sys.modules.get('gevent', None)
            gpyver = 'GPython %s' % golang.__version__
            if gevent is not None:
                gpyver += ' [gevent %s]' % gevent.__version__
            else:
                gpyver += ' [threads]'
            ver.append(gpyver)

        import platform
        pyimpl = platform.python_implementation()

        v = _version_info_str
        if pyimpl == 'CPython':
            ver.append('CPython %s' % v(sys.version_info))
        elif pyimpl == 'PyPy':
            ver.append('PyPy %s'   % v(sys.pypy_version_info))
            ver.append('Python %s' % v(sys.version_info))
        else:
            ver = [] # unknown

        ver = ' / '.join(ver)
        if ver == '':
            # unknown implementation: just print full sys.version
            ver = sys.version

        print(ver, file=sys.stderr)
        return

    # init warnings
    if len(warnoptions) > 0:
        # NOTE warnings might be already imported by code that calls pymain.
        # This way we cannot set `sys.warnoptions = warnoptions` and just
        # import/reload warnings (if we reload warnings, it will loose all
        # previous setup that pymain caller might have done to it).
        # -> only amend warnings setup
        #
        # NOTE $PYTHONWARNINGS is handled by underlying python natively.
        import warnings
        sys.warnoptions += warnoptions
        warnings._processoptions(warnoptions)

    # execute -m/-c/file/interactive
    run()


# execfile was removed in py3
def _execfile(path, globals=None, locals=None):
    import six
    with open(path, "rb") as f:
        src = f.read()
    code = compile(src, path, 'exec')
    six.exec_(code, globals, locals)

# _version_info_str converts version_info -> str.
def _version_info_str(vi):
    major, minor, micro, release, serial = vi
    v = '%d.%d.%d' % (major, minor, micro)
    if (release, serial) != ('final', 0):
        v += '.%s%s' % (release, serial)
    return v


def main():
    # import sys early.
    # it is ok to import sys before gevent because sys is anyway always
    # imported first, e.g. to support sys.modules.
    import sys

    # safety check that we are not running from a setuptools entrypoint, where
    # it would be too late to monkey-patch stdlib.
    #
    # (os and signal are imported by python startup itself)
    # (on py3 _thread is imported by the interpreter early to support fine-grained import lock)
    avoid = ['pkg_resources', 'golang', 'socket', 'select', 'threading',
             'thread', 'ssl', 'subprocess']
    # pypy7 made time always pre-imported (https://bitbucket.org/pypy/pypy/commits/6759b768)
    # cpython3.8 made time always pre-imported via zipimport hook:
    # https://github.com/python/cpython/commit/79d1c2e6c9d1 (`import time` in zipimport.py)
    pypy = ('PyPy' in sys.version)
    if (not pypy) and (sys.version_info < (3, 8)):
        avoid.append('time')
    bad = []
    for mod in avoid:
        if mod in sys.modules:
            bad.append(mod)
    if bad:
        sysmodv = list(sys.modules.keys())
        sysmodv.sort()
        raise RuntimeError('gpython: internal error: the following modules are pre-imported, but must be not:'
                '\n\n\t%s\n\nsys.modules:\n\n\t%s' % (bad, sysmodv))

    # set UTF-8 as default encoding.
    if sys.getdefaultencoding() != 'utf-8':
        reload(sys)
        sys.setdefaultencoding('utf-8')
        delattr(sys, 'setdefaultencoding')

    # sys.executable
    # on windows there are
    #   gpython-script.py
    #   gpython.exe
    #   gpython.manifest
    # and argv[0] is gpython-script.py
    exe  = sys.argv[0]
    argv = sys.argv[1:]
    if exe.endswith('-script.py'):
        exe = exe[:-len('-script.py')]
        exe = exe + '.exe'
    sys._gpy_underlying_executable = sys.executable
    sys.executable  = exe

    # import os to get access to environment.
    # it is practically ok to import os before gevent, because os is always
    # imported by site. Yes, `import site` can be disabled by -S, but there is
    # no harm wrt gevent monkey-patching even if we import os first.
    import os

    # `python /path/to/gpython` adds /path/to to sys.path[0] - remove it.
    # `gpython file` will add path-to-file to sys.path[0] by itself, and
    # /path/to/gpython is unneccessary and would create difference in behaviour
    # in between gpython and python.
    exedir = exe[:exe.rindex(os.sep)] # dirname, but os.path cannot be imported yet
    if sys.path[0] != exedir:
        raise RuntimeError('gpython: internal error: sys.path[0] was not set by underlying python to dirname(gpython):'
                '\n\n\tgpython:\t%s\n\tsys.path[0]:\t%s' % (exe, sys.path[0]))
    del sys.path[0]

    # extract and process -X
    # -X gpython.runtime=(gevent|threads)    + $GPYTHON_RUNTIME
    sys._xoptions = getattr(sys, '_xoptions', {})
    argv_ = []
    gpy_runtime = os.getenv('GPYTHON_RUNTIME', 'gevent')
    while len(argv) > 0:
        arg  = argv[0]
        argv = argv[1:]

        if not arg.startswith('-X'):
            argv_.append(arg)
            # continue looking for -X only until options end
            if not arg.startswith('-'):
                break
            continue

        # -X <opt>
        opt = arg[2:]       # -X<opt>
        if opt == '':
            opt  = argv[0]  # -X <opt>
            argv = argv[1:]

        if opt.startswith('gpython.runtime='):
            gpy_runtime = opt[len('gpython.runtime='):]
            sys._xoptions['gpython.runtime'] = gpy_runtime

        else:
            raise RuntimeError('gpython: unknown -X option %s' % opt)
    argv = argv_ + argv

    # init initializes according to selected runtime
    # it is called after options are parsed and sys.path is setup correspondingly.
    # this way golang and gevent are imported from exactly the same place as
    # they would be in standard python after regular import (ex from golang/
    # under cwd if run under `python -c ...` or interactive console.
    def init():
        if gpy_runtime == 'gevent':
            # make gevent pre-available & stdlib patched
            import gevent
            from gevent import monkey
            # XXX workaround for gevent vs pypy2 crash.
            # XXX remove when gevent-1.4.1 is relased (https://github.com/gevent/gevent/pull/1357).
            patch_thread=True
            if pypy and sys.version_info.major == 2:
                _ = monkey.patch_thread(existing_locks=False)
                assert _ in (True, None)
                patch_thread=False
            _ = monkey.patch_all(thread=patch_thread)      # XXX sys=True ?
            if _ not in (True, None):   # patched or nothing to do
                # XXX provide details
                raise RuntimeError('gevent monkey-patching failed')
            gpy_verextra = 'gevent %s' % gevent.__version__

        elif gpy_runtime == 'threads':
            gpy_verextra = 'threads'

        else:
            raise RuntimeError('gpython: invalid runtime %s' % gpy_runtime)

        # put go, chan, select, ... into builtin namespace
        import golang
        from six.moves import builtins
        for k in golang.__all__:
            setattr(builtins, k, getattr(golang, k))

        # sys.version
        sys.version += (' [GPython %s] [%s]' % (golang.__version__, gpy_verextra))

    # tail to pymain
    pymain(argv, init)

if __name__ == '__main__':
    main()
