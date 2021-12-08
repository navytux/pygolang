#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021  Nexedi SA and Contributors.
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


_pyopt = "c:im:OVW:X:"
_pyopt_long = ('version',)

# pymain mimics `python ...`
#
# argv is full argument vector including first [0] for path to main program itself.
# init, if provided, is called after options are parsed, but before interpreter start.
def pymain(argv, init=None):
    import sys
    from os.path import dirname, realpath

    # sys.executable
    # on windows there are
    #   gpython-script.py
    #   gpython.exe
    #   gpython.manifest
    # and argv[0] is gpython-script.py
    exe  = realpath(argv[0])
    argv = argv[1:]
    if exe.endswith('-script.py'):
        exe = exe[:-len('-script.py')]
        exe = exe + '.exe'
    sys._gpy_underlying_executable = sys.executable
    sys.executable  = exe

    # `python /path/to/gpython` adds /path/to to sys.path[0] - remove it.
    # `gpython file` will add path-to-file to sys.path[0] by itself, and
    # /path/to/gpython is unnecessary and would create difference in behaviour
    # in between gpython and python.
    exedir = dirname(exe)
    if sys.path[0] == exedir:
        del sys.path[0]
    else:
        # buildout injects `sys.path[0:0] = eggs` into python scripts.
        # detect that and remove sys.path entry corresponding to exedir.
        if not _is_buildout_script(exe):
            raise RuntimeError('pymain: internal error: sys.path[0] was not set by underlying python to dirname(exe):'
                    '\n\n\texe:\t%s\n\tsys.path[0]:\t%s' % (exe, sys.path[0]))
        else:
            if exedir in sys.path:
                sys.path.remove(exedir)
            else:
                raise RuntimeError('pymain: internal error: sys.path does not contain dirname(exe):'
                    '\n\n\texe:\t%s\n\tsys.path:\t%s' % (exe, sys.path))



    run = None          # function to run according to -c/-m/file/stdin/interactive
    version = False     # set if `-V`
    warnoptions = []    # collected `-W arg`
    reexec_with = []    # reexecute underlying python with those options (e.g. -O, -S, ...)
    reexec_argv = []    # if reexecuting, reexecute with this application-level argv
    inspect = False     # inspect interactively at the end

    igetopt = _IGetOpt(argv, _pyopt, _pyopt_long)
    for (opt, arg) in igetopt:
        # options that require reexecuting through underlying python with that -<opt>
        if opt in (
                '-O',   # optimize
            ):
            reexec_with.append(opt)
            if arg is not None:
                reexec_with.append(arg)
            continue

        reexec_argv.append(opt)
        if arg is not None:
            reexec_argv.append(arg)


        # -V / --version
        if opt in ('-V', '--version'):
            version = True
            break

        # -c command
        elif opt == '-c':
            cmd = arg
            sys.argv = ['-c'] + igetopt.argv # python leaves '-c' as argv[0]
            sys.path.insert(0, '')   # cwd
            def run(mmain):
                import six
                six.exec_(cmd, mmain.__dict__)
            break

        # -m module
        elif opt == '-m':
            mod = arg
            sys.argv = [mod] + igetopt.argv
            # sys.path <- cwd
            # NOTE python2 injects '', while python3 injects realpath('')
            # we stick to python3 behaviour, as it is more sane because e.g.
            # import path does not change after chdir.
            sys.path.insert(0, realpath(''))  # realpath(cwd)
            def run(mmain):
                import runpy
                # search sys.path for module and run corresponding .py file as script
                # NOTE runpy._run_module_as_main works on sys.modules['__main__']
                sysmain = sys.modules['__main__']
                assert sysmain is mmain,  (sysmain, mmain)
                runpy._run_module_as_main(mod)
            break

        # -W arg  (warning control)
        elif opt == '-W':
            warnoptions.append(arg)

        # -i inspect interactively
        elif opt == '-i':
            inspect = True

        else:
            print("unknown option: '%s'" % opt, file=sys.stderr)
            sys.exit(2)

    argv = igetopt.argv
    reexec_argv += argv
    if run is None:
        # file
        if len(argv) > 0 and argv[0] != '-':
            sys.argv = argv
            filepath = argv[0]
            # starting from cpython 3.9 __file__ is always absolute
            # https://bugs.python.org/issue20443
            if sys.version_info >= (3, 9):
                filepath = realpath(filepath)

            sys.path.insert(0, realpath(dirname(filepath))) # not abspath -> see PySys_SetArgvEx
            def run(mmain):
                mmain.__file__ = filepath
                _execfile(filepath, mmain.__dict__)

        # interactive console / program on non-tty stdin
        else:
            sys.argv = ['']  if len(argv) == 0  else  argv # e.g. ['-']
            sys.path.insert(0, '')  # cwd

            if sys.stdin.isatty() or inspect:
                inspect = False # no console after console
                def run(mmain):
                    mmain.__file__ = '<stdin>'
                    _interact(mmain)
            else:
                def run(mmain):
                    import six
                    prog = sys.stdin.read()
                    mmain.__file__ = '<stdin>'
                    six.exec_(prog, mmain.__dict__)


    # ---- options processed -> start the interpreter ----

    # reexec underlying interpreter on options that we cannot handle at python
    # level after underlying interpreter is already started. For example
    #
    #   gpython -O file.py
    #
    # is reexecuted as
    #
    #   python -O gpython file.py
    if len(reexec_with) > 0:
        import os
        argv = [sys._gpy_underlying_executable] + reexec_with + [sys.executable] + reexec_argv
        os.execv(argv[0], argv)

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

    # inject new empty __main__ module instead of previous __main__
    import types
    mmain = types.ModuleType('__main__')
    mmain.__file__    = None
    mmain.__loader__  = None
    mmain.__package__ = None
    mmain.__doc__     = None
    sys.modules['__main__'] = mmain

    # execute -m/-c/file/interactive
    import traceback
    try:
        run(mmain)
    except:
        # print exception becore going to interactive inspect
        if inspect:
            traceback.print_exc()
        else:
            raise
    finally:
        # interactive inspect
        if inspect:
            _interact(mmain, banner='')


# _interact runs interactive console in mmain namespace.
def _interact(mmain, banner=None):
    import code, sys
    from six.moves import input as raw_input
    # like code.interact() but with overridden console.raw_input _and_
    # readline imported (code.interact mutually excludes those two).
    try:
        import readline # enable interactive editing
    except ImportError:
        pass

    console = code.InteractiveConsole(mmain.__dict__)
    def _(prompt):
        # python behaviour:
        # - use stdout for prompt by default;
        # - use stderr for prompt if any of stdin/stderr is not a tty
        # (builtin raw_input always prints prompt)
        promptio = sys.stdout
        if (not sys.stdin.isatty()) or (not sys.stdout.isatty()):
            promptio = sys.stderr
        promptio.write(prompt)
        promptio.flush()
        return raw_input('')
    console.raw_input = _

    console.interact(banner=banner)


# execfile was removed in py3
def _execfile(path, globals=None, locals=None):
    import six
    with open(path, "rb") as f:
        src = f.read()
    code = compile(src, path, 'exec', dont_inherit=True)
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
    # pypy7 made time always pre-imported (https://foss.heptapod.net/pypy/pypy/-/commit/f4fa167b)
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


    # import os to get access to environment.
    # it is practically ok to import os before gevent, because os is always
    # imported by site. Yes, `import site` can be disabled by -S, but there is
    # no harm wrt gevent monkey-patching even if we import os first.
    import os

    # extract and process `-X gpython.*`
    # -X gpython.runtime=(gevent|threads)    + $GPYTHON_RUNTIME
    sys._xoptions = getattr(sys, '_xoptions', {})
    argv_ = []
    gpy_runtime = os.getenv('GPYTHON_RUNTIME', 'gevent')
    igetopt = _IGetOpt(sys.argv[1:], _pyopt, _pyopt_long)
    for (opt, arg) in igetopt:
        if opt == '-X':
            if arg.startswith('gpython.'):
                if arg.startswith('gpython.runtime='):
                    gpy_runtime = arg[len('gpython.runtime='):]
                    sys._xoptions['gpython.runtime'] = gpy_runtime

                else:
                    raise RuntimeError('gpython: unknown -X option %s' % opt)

                continue

        argv_.append(opt)
        if arg is not None:
            argv_.append(arg)

        # options after -c / -m are not for python itself
        if opt in ('-c', '-m'):
            break

    argv = [sys.argv[0]] + argv_ + igetopt.argv

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
            # XXX remove when gevent-1.4.1 is released (https://github.com/gevent/gevent/pull/1357).
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


# _is_buildout_script returns whether file @path is generated as python buildout script.
def _is_buildout_script(path):
    with open(path, 'r') as f:
        src = f.read()
    # buildout injects the following prologues into python scripts:
    #   sys.path[0:0] = [
    #     ...
    #   ]
    return ('\nsys.path[0:0] = [\n' in src)


# _IGetOpt provides getopt-style incremental options parsing.
# ( we cannot use getopt directly, because it complains about "unrecognized options"
#   on e.g. `gpython file.py -opt` )
class _IGetOpt:
    def __init__(self, argv, shortopts, longopts):
        self.argv = argv
        self._opts = {}         # opt -> bool(arg-required)
        self._shortopttail = '' # current tail of short options from e.g. -abcd
        # parse shortopts -> ._opts
        opt = None
        for _ in shortopts:
            if _ == ':':
                if opt is None:
                    raise RuntimeError("invalid shortopts: unexpected ':'")
                self._opts['-'+opt] = True
                opt = None # prevent ::

            else:
                opt = _
                if opt in self._opts:
                    raise RuntimeError("invalid shortopts: double '%s'" % opt)
                self._opts['-'+opt] = False

        # parse longopts -> ._opts
        for opt in longopts:
            arg_required = (opt[-1:] == '=')
            if arg_required:
                opt = opt[:-1]
            self._opts['--'+opt] = arg_required


    def __iter__(self):
        return self
    def __next__(self):
        # yield e.g. -b -c -d  from -abcd
        if len(self._shortopttail) > 0:
            opt = '-'+self._shortopttail[0]
            self._shortopttail = self._shortopttail[1:]

            if opt not in self._opts:
                raise RuntimeError('unexpected option %s' % opt)

            arg = None
            if self._opts[opt]: # arg required
                if len(self._shortopttail) > 0:
                    # -o<arg>
                    arg = self._shortopttail
                    self._shortopttail = ''
                else:
                    # -o <arg>
                    if len(self.argv) == 0:
                        raise RuntimeError('option %s requires an argument' % opt)
                    arg = self.argv[0]
                    self.argv = self.argv[1:]

            return (opt, arg)

        # ._shortopttail is empty - proceed with .argv

        if len(self.argv) == 0:
            raise StopIteration # end of argv

        opt = self.argv[0]
        if not opt.startswith('-'):
            raise StopIteration # not an option

        if opt == '-':
            raise StopIteration # not an option

        self.argv = self.argv[1:]

        if opt == '--':
            raise StopIteration # options -- args delimiter

        # short option
        if not opt.startswith('--'):
            self._shortopttail = opt[1:]
            return self.__next__()

        # long option
        arg = None
        if '=' in opt:
            opt, arg = opt.split('=')
        if opt not in self._opts:
            raise RuntimeError('unexpected option %s' % opt)
        arg_required = self._opts[opt]
        if not arg_required:
            if arg is not None:
                raise RuntimeError('option %s requires no argument' % opt)
        else:
            if arg is None:
                if len(self.argv) == 0:
                    raise RuntimeError('option %s requires no argument' % opt)
                arg = self.argv[0]
                self.argv[0] = self.argv[1:]

        return (opt, arg)

    next = __next__ # for py2


if __name__ == '__main__':
    main()
