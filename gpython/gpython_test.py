# -*- coding: utf-8 -*-
# Copyright (C) 2019-2025  Nexedi SA and Contributors.
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

from __future__ import print_function, absolute_import

import sys, os, platform, re, golang
from golang.golang_test import pyout, pyrun, _pyrun, readfile
from subprocess import PIPE
from six import PY2, PY3
from six.moves import builtins
import pytest

from os.path import join, dirname, realpath
here     = dirname(__file__)
testdata = join(here, 'testdata')
testprog = join(here, 'testprog')

is_pypy    = (platform.python_implementation() == 'PyPy')
is_cpython = (platform.python_implementation() == 'CPython')
is_gpython = ('GPython' in sys.version)

# @gpython_only is marker to run a test only under gpython
gpython_only = pytest.mark.skipif(not is_gpython, reason="gpython-only test")

# runtime is pytest fixture that yields all variants of should be supported gpython runtimes:
# '' - not specified (gpython should autoselect)
# 'gevent'
# 'threads'
@pytest.fixture(scope="function", params=['', 'gevent', 'threads'])
def runtime(request):
    yield request.param

# gpyenv returns environment appropriate for spawning gpython with
# specified runtime.
def gpyenv(runtime): # -> env
    env = os.environ.copy()
    if runtime != '':
        env['GPYTHON_RUNTIME'] = runtime
    else:
        env.pop('GPYTHON_RUNTIME', None)
    return env


@gpython_only
def test_defaultencoding_utf8():
    assert sys.getdefaultencoding() == 'utf-8'

@gpython_only
def test_golang_builtins():
    # some direct accesses
    assert go     is golang.go
    assert chan   is golang.chan
    assert select is golang.select
    assert error  is golang.error
    assert b      is golang.b
    assert u      is golang.u
    assert bstr   is golang.bstr
    assert ustr   is golang.ustr
    assert biter  is golang.biter
    assert uiter  is golang.uiter
    assert bbyte  is golang.bbyte
    assert uchr   is golang.uchr

    # indirectly verify golang.__all__
    for k in golang.__all__:
        assert getattr(builtins, k) is getattr(golang, k)

@gpython_only
def test_gevent_activated():
    # gpython, by default, activates gevent.
    # handling of various runtime modes is explicitly tested in test_Xruntime.
    assert_gevent_activated()

def assert_gevent_activated():
    assert 'gevent' in sys.modules
    from gevent.monkey import is_module_patched as patched, is_object_patched as obj_patched

    # builtin (gevent: only on py2 - on py3 __import__ uses fine-grained locking)
    if PY2:
        assert obj_patched('__builtin__', '__import__')

    assert patched('socket')
    # patch_socket(dns=True) also patches vvv
    assert obj_patched('socket', 'getaddrinfo')
    assert obj_patched('socket', 'gethostbyname')
    # ...

    assert patched('time')

    assert patched('select')
    import select as select_mod # patch_select(aggressive=True) removes vvv
    assert not hasattr(select_mod, 'epoll')
    assert not hasattr(select_mod, 'kqueue')
    assert not hasattr(select_mod, 'kevent')
    assert not hasattr(select_mod, 'devpoll')

    # XXX on native windows, patch_{os,signal} do nothing currently
    if os.name != 'nt':
        assert patched('os')
        assert patched('signal')

    assert patched('thread' if PY2 else '_thread')
    assert patched('threading')
    assert patched('_threading_local')

    assert patched('ssl')
    assert patched('subprocess')
    #assert patched('sys')       # currently disabled

    if sys.hexversion >= 0x03070000: # >= 3.7.0
        assert patched('queue')

def assert_gevent_not_activated():
    assert 'gevent' not in sys.modules
    from gevent.monkey import is_module_patched as patched, is_object_patched as obj_patched

    assert not patched('socket')
    assert not patched('time')
    assert not patched('select')
    assert not patched('os')
    assert not patched('signal')
    assert not patched('thread' if PY2 else '_thread')
    assert not patched('threading')
    assert not patched('_threading_local')
    assert not patched('ssl')
    assert not patched('subprocess')
    assert not patched('sys')


@gpython_only
def test_executable(runtime):
    # sys.executable must point to gpython and we must be able to execute it.
    import gevent
    assert 'gpython' in sys.executable
    ver = pyout(['-c', 'import sys; print(sys.version)'], env=gpyenv(runtime))
    ver = str(ver)
    assert ('[GPython %s]' % golang.__version__) in ver
    if runtime != 'threads':
        assert ('[gevent %s]'  % gevent.__version__)     in ver
        assert ('[threads]')                         not in ver
    else:
        assert ('[gevent ')                          not in ver
        assert ('[threads]')                             in ver


# verify pymain.
#
# !gpython_only to make sure we get the same output when run via pymain (under
# gpython) and plain python (!gpython).
def test_pymain():
    from golang import b

    # stdin
    _ = pyout([], stdin=b'import hello\n', cwd=testdata)
    assert _ == b"hello\nworld\n['']\n"
    _ = pyout(['-'], stdin=b'import hello\n', cwd=testdata)
    assert _ == b"hello\nworld\n['-']\n"
    _ = pyout(['-', 'zzz'], stdin=b'import hello\n', cwd=testdata)
    assert _ == b"hello\nworld\n['-', 'zzz']\n"

    # -c <command>
    _ = pyout(['-c', 'import hello', 'abc', 'def'], cwd=testdata)
    assert _ == b"hello\nworld\n['-c', 'abc', 'def']\n"
    # -c<command> should also work
    __ = pyout(['-cimport hello', 'abc', 'def'], cwd=testdata)
    assert __ == _

    # -m <module>
    _ = pyout(['-m', 'hello', 'abc', 'def'], cwd=testdata)
    # realpath rewrites e.g. `local/lib -> lib` if local/lib is symlink
    hellopy = realpath(join(testdata, 'hello.py'))
    assert _ == b"hello\nworld\n[%s, 'abc', 'def']\n" % b(repr(hellopy))
    # -m<module>
    __ = pyout(['-mhello', 'abc', 'def'], cwd=testdata)
    assert __ == _
    # -m <package> with __main__.py
    _ = pyout(['-m', 'pkg', 'abc', 'def'], cwd=testdata)
    pkgmainpy = realpath(join(testdata, 'pkg', '__main__.py'))
    assert _ == b"pkg/__main__\npkg/mod\n[%s, 'abc', 'def']\n" % b(repr(pkgmainpy))
    # -m <package>.<module>
    _ = pyout(['-m', 'pkg.mod'], cwd=testdata)
    assert _ == b"pkg/mod\n"

    # -m <module> inside zip
    zbundle = join(testdata, 'bundle.zip')
    with_zbundle  = {'envadj': {'PYTHONPATH': zbundle}}
    _ = pyout(['-m', 'hello', 'abc', 'def'], **with_zbundle)
    zhellopy = join(zbundle, 'hello.py')
    assert _ == b"zhello\nzworld\n[%s, 'abc', 'def']\n" % b(repr(zhellopy))
    # -m <package> with __main__.py inside zip
    _ = pyout(['-m', 'pkg', 'abc', 'def'], **with_zbundle)
    zpkgmainpy = join(zbundle, 'pkg', '__main__.py')
    assert _ == b"zpkg/__main__\nzpkg/mod\n[%s, 'abc', 'def']\n" % b(repr(zpkgmainpy))
    # -m <package>.<module> inside zip
    _ = pyout(['-m', 'pkg.mod'], **with_zbundle)
    assert _ == b"zpkg/mod\n"


    # file
    _ = pyout(['testdata/hello.py', 'abc', 'def'], cwd=here)
    assert _ == b"hello\nworld\n['testdata/hello.py', 'abc', 'def']\n"

    # dir with __main__.py
    _ = pyout(['testdata/dir', 'abc', 'def'], cwd=here)
    assert _ == b"dir/__main__\ndir/mod\n['testdata/dir', 'abc', 'def']\n"

    # dir.zip with __main__.py
    _ = pyout(['testdata/dir.zip', 'abc', 'def'], cwd=here)
    assert _ == b"zdir/__main__\nzdir/mod\n['testdata/dir.zip', 'abc', 'def']\n"

    # -i after stdin (also tests interactive mode as -i forces interactive even on non-tty)
    d = {
        b'repr(hellopy)':       b(repr(hellopy)),
        b'repr(pkgmainpy)':     b(repr(pkgmainpy)),
        b'repr(zhellopy)':      b(repr(zhellopy)),
        b'repr(zpkgmainpy)':    b(repr(zpkgmainpy)),
        b'ps1':                 b'' # cpython emits prompt to stderr
    }
    if is_pypy and not is_gpython:
        d[b'ps1'] = b'>>>> ' # native pypy emits prompt to stdout and >>>> instead of >>>
    _ = pyout(['-i'], stdin=b'import hello\n', cwd=testdata)
    assert _ == b"%(ps1)shello\nworld\n['']\n%(ps1)s"           % d
    _ = pyout(['-i', '-'], stdin=b'import hello\n', cwd=testdata)
    assert _ == b"%(ps1)shello\nworld\n['-']\n%(ps1)s"          % d
    _ = pyout(['-i', '-', 'zzz'], stdin=b'import hello\n', cwd=testdata)
    assert _ == b"%(ps1)shello\nworld\n['-', 'zzz']\n%(ps1)s"   % d

    # -i after -c
    _ = pyout(['-i', '-c', 'import hello'], stdin=b'hello.tag', cwd=testdata)
    assert _ == b"hello\nworld\n['-c']\n%(ps1)s'~~HELLO~~'\n%(ps1)s"    % d

    # -i after -m <module>
    _ = pyout(['-i', '-m', 'hello'], stdin=b'world.tag', cwd=testdata)
    assert _ == b"hello\nworld\n[%(repr(hellopy))s]\n%(ps1)s'~~WORLD~~'\n%(ps1)s"  % d
    # -i after -m <package> with __main__.py
    _ = pyout(['-i', '-m', 'pkg'], stdin=b'mod.tag', cwd=testdata)
    assert _ == b"pkg/__main__\npkg/mod\n[%(repr(pkgmainpy))s]\n%(ps1)s'~~PKG/MOD~~'\n%(ps1)s" % d
    # -i after -m <package>.<module>
    _ = pyout(['-i', '-m', 'pkg.mod'], stdin=b'tag', cwd=testdata)
    assert _ == b"pkg/mod\n%(ps1)s'~~PKG/MOD~~'\n%(ps1)s" % d

    # -i after -m <module> inside zip
    _ = pyout(['-i', '-m', 'hello'], stdin=b'world.tag', **with_zbundle)
    assert _ == b"zhello\nzworld\n[%(repr(zhellopy))s]\n%(ps1)s'~~ZWORLD~~'\n%(ps1)s"  % d
    # -i after -m <package> with __main__.py inside zip
    _ = pyout(['-i', '-m', 'pkg'], stdin=b'mod.tag', **with_zbundle)
    assert _ == b"zpkg/__main__\nzpkg/mod\n[%(repr(zpkgmainpy))s]\n%(ps1)s'~~ZPKG/MOD~~'\n%(ps1)s" % d
    # -i after -m <package>.<module> inside zip
    _ = pyout(['-i', '-m', 'pkg.mod'], stdin=b'tag', **with_zbundle)
    assert _ == b"zpkg/mod\n%(ps1)s'~~ZPKG/MOD~~'\n%(ps1)s" % d

    # -i after file
    _ = pyout(['-i', 'testdata/hello.py'], stdin=b'tag', cwd=here)
    assert _ == b"hello\nworld\n['testdata/hello.py']\n%(ps1)s'~~HELLO~~'\n%(ps1)s" % d
    # -i after dir with __main__.py
    _ = pyout(['-i', 'testdata/dir'], stdin=b'mod.tag', cwd=here)
    assert _ == b"dir/__main__\ndir/mod\n['testdata/dir']\n%(ps1)s'~~DIR/MOD~~'\n%(ps1)s" % d
    # -i after dir.zip with __main__.py
    _ = pyout(['-i', 'testdata/dir.zip'], stdin=b'mod.tag', cwd=here)
    assert _ == b"zdir/__main__\nzdir/mod\n['testdata/dir.zip']\n%(ps1)s'~~ZDIR/MOD~~'\n%(ps1)s" % d


    # -W <opt>
    _ = pyout(['-Werror', '-Whello', '-W', 'ignore::DeprecationWarning',
               'testprog/print_warnings_setup.py'], cwd=here)
    assert re.match(
        br"sys\.warnoptions: \['error', 'hello', 'ignore::DeprecationWarning'\]\n\n"
        br"warnings\.filters:\n"
        br"(- [^\n]+\n)*" # Additional filters added by automatically imported modules
        br"- ignore::DeprecationWarning::\*\n"
        br"- error::Warning::\*\n"
        br"(- [^\n]+\n)*", # Remaining filters
        _,
    )
    # $PYTHONWARNINGS
    _ = pyout(['testprog/print_warnings_setup.py'], cwd=here,
              envadj={'PYTHONWARNINGS': 'ignore,world,error::SyntaxWarning'})
    assert re.match(
        br"sys\.warnoptions: \['ignore', 'world', 'error::SyntaxWarning'\]\n\n"
        br"warnings\.filters:\n"
        br"(- [^\n]+\n)*" # Additional filters added by automatically imported modules
        br"- error::SyntaxWarning::\*\n"
        br"- ignore::Warning::\*\n"
        br"(- [^\n]+\n)*", # Remaining filters
        _,
    )


def test_pymain_print_function_future():
    if PY2:
        _ = pyout([], stdin=b'print "print", "is", "a", "statement"\n')
        assert _ == b"print is a statement\n"
        _ = pyout(['-c', 'print "print", "is", "a", "statement"'])
        assert _ == b"print is a statement\n"
        _ = pyout(['print_statement.py'], cwd=testprog)
        assert _ == b"print is a statement\n"
    _ = pyout(['future_print_function.py'], cwd=testprog)
    assert _ == b"print is a function with print_function future\n"


# verify that pymain runs programs with __main__ module correctly setup.
def test_pymain__main__():
    from golang import b
    check_main_py = readfile('%s/check_main.py' % testprog)

    pyrun(['testprog/check_main.py'], cwd=here) # file
    pyrun(['-m', 'check_main'], cwd=testprog)   # -m
    pyrun(['-c', check_main_py])                # -c

    # stdin
    ret, out, err = _pyrun([], stdin=b(check_main_py), stdout=PIPE, stderr=PIPE)
    assert ret == 0,    (out, err)
    assert b"Error" not in out,    (out, err)
    assert b"Error" not in err,    (out, err)


# verify that pymain sets sys.path in exactly the same way as underlying python does.
@gpython_only
def test_pymain_syspath():
    from gpython import _is_buildout_script
    if _is_buildout_script(sys.executable):
        pytest.xfail("with buildout raw underlying interpreter does not have " +
                     "access to installed eggs")
    # check verifies that print_syspath output for gpython and underlying python is the same.
    # if path0cwd2realpath=Y, expect realpath('') instead of '' in sys.path[0]
    # if path0realpath2cwd=Y, expect '' instead of realpath('') in sys.path[0]
    def check(argv, path0cwd2realpath=False, path0realpath2cwd=False, **kw):
        realcwd = realpath(kw.get('cwd', ''))
        assert not (path0cwd2realpath and path0realpath2cwd)
        def _(gpyoutv, stdpyoutv):
            if path0cwd2realpath:
                assert stdpyoutv[0] == ''
                stdpyoutv[0] = realcwd
            if path0realpath2cwd:
                assert stdpyoutv[0] == realcwd
                stdpyoutv[0] = ''
            # gpython imports golang, which imports setuptools_dso, which imports setuptools
            # which, starting from setuptools 71, appends .../setuptools/_vendor to sys.path
            #
            #    https://github.com/pypa/setuptools/commit/d4352b5d
            #
            # filter that out.
            #
            # TODO consider improving setuptools_dso.runtime not to import setuptools at all instead
            if gpyoutv[-1].endswith('/setuptools/_vendor'):
                del gpyoutv[-1]

        check_gpy_vs_py(argv, postprocessf=_, **kw)

    check([], stdin=b'import print_syspath', cwd=testprog,  # stdin
            path0realpath2cwd=(PY3 and is_pypy)) # https://foss.heptapod.net/pypy/pypy/-/issues/3610
    check(['-c', 'import print_syspath'], cwd=testprog)     # -c
    check(['-m', 'print_syspath'], cwd=testprog,            # -m
            path0cwd2realpath=PY2)
    check(['testprog/print_syspath.py'], cwd=here)          # file


# verify that pymain handles -O in exactly the same way as underlying python does.
@gpython_only
def test_pymain_opt():
    def check(argv):
        argv += ["print_opt.py"]
        kw = {'cwd': testprog}
        check_gpy_vs_py(argv, **kw)

    check([])
    check(["-O"])
    if not (is_pypy and PY2): # https://foss.heptapod.net/pypy/pypy/-/issues/3356
        check(["-OO"])
        check(["-OOO"])
        check(["-O", "-O"])
        check(["-O", "-O", "-O"])

# verify that pymain handles -E in exactly the same way as underlying python does.
@gpython_only
def test_pymain_E():
    envadj = {'PYTHONOPTIMIZE': '1'}
    def sys_flags_optimize(level):
        return 'sys.flags.optimize:   %s' % level

    # without -E $PYTHONOPTIMIZE should be taken into account
    def _(gpyoutv, stdpyoutv):
        assert sys_flags_optimize(0) not in stdpyoutv
        assert sys_flags_optimize(0) not in gpyoutv
        assert sys_flags_optimize(1)     in stdpyoutv
        assert sys_flags_optimize(1)     in gpyoutv
    check_gpy_vs_py(['testprog/print_opt.py'], _, envadj=envadj, cwd=here)

    # with -E not
    def _(gpyoutv, stdpyoutv):
        assert sys_flags_optimize(0)     in stdpyoutv
        assert sys_flags_optimize(0)     in gpyoutv
        assert sys_flags_optimize(1) not in stdpyoutv
        assert sys_flags_optimize(1) not in gpyoutv
    check_gpy_vs_py(['-E', 'testprog/print_opt.py'], _, envadj=envadj, cwd=here)


# verify that pymain handles -X non-gpython-option in exactly the same way as underlying python does.
@pytest.mark.skipif(PY2, reason="-X does not work at all on plain cpython2")
@gpython_only
def test_pymain_X():
    check_gpy_vs_py(['testprog/print_faulthandler.py'], cwd=here)
    check_gpy_vs_py(['-X', 'faulthandler', 'testprog/print_faulthandler.py'], cwd=here)


# pymain -u
@gpython_only
def test_pymain_u():
    _check_gpy_vs_py([      'testprog/print_stdio_bufmode.py'], cwd=here)
    _check_gpy_vs_py(['-u', 'testprog/print_stdio_bufmode.py'], cwd=here)


# pymain -v
@gpython_only
def test_pymain_v():
    def nimport(argv, **kw):
        argv = argv + ['testdata/hello.py']
        kw.setdefault('cwd', here)
        ret, out, err = _pyrun(argv, stdout=PIPE, stderr=PIPE, **kw)
        assert ret == 0,    (out, err)
        n = 0
        for _ in u(err).splitlines():
            if _.startswith("import "):
                n += 1
        return n

    # without -v there must be no "import ..." messages
    assert nimport([])                                              == 0
    assert nimport([], pyexe=sys._gpy_underlying_executable)        == 0

    # with    -v there must be many "import ..." messages
    assert nimport(['-v'])                                          >  10
    assert nimport(['-v'], pyexe=sys._gpy_underlying_executable)    >  10


# pymain -V/--version
# gpython_only because output differs from !gpython.
@gpython_only
def test_pymain_ver(runtime):
    from golang import b
    from gpython import _version_info_str as V
    import gevent
    vok = 'GPython %s' % golang.__version__
    if runtime != 'threads':
        vok += ' [gevent %s]' % gevent.__version__
    else:
        vok += ' [threads]'

    if is_cpython:
        vok += ' / CPython %s' % platform.python_version()
    elif is_pypy:
        vok += ' / PyPy %s / Python %s' % (V(sys.pypy_version_info), V(sys.version_info))
    else:
        vok = sys.version

    vok += '\n'

    ret, out, err = _pyrun(['-V'], stdout=PIPE, stderr=PIPE, env=gpyenv(runtime))
    assert (ret, out, b(err)) == (0, b'', b(vok))

    ret, out, err = _pyrun(['--version'], stdout=PIPE, stderr=PIPE, env=gpyenv(runtime))
    assert (ret, out, b(err)) == (0, b'', b(vok))

# pymain --unknown/-Z option
# gpython_only because output differs from !gpython
@gpython_only
def test_pymain_unknown():
    from golang import b
    def check(argv, errok):
        ret, out, err = _pyrun(argv, stdout=PIPE, stderr=PIPE)
        assert b(errok) in b(err)
        assert ret != 0

    check(['-Z'],                   "unexpected option -Z")
    check(['-Z=xyz'],               "unexpected option -Z")
    check(['-Z=xyz=pqr'],           "unexpected option -Z")
    check(['--unknown'],            "unexpected option --unknown")
    check(['--unknown=xyz'],        "unexpected option --unknown")
    check(['--unknown=xyz=pqr'],    "unexpected option --unknown")

# verify that ./bin/gpython runs ok.
@gpython_only
def test_pymain_run_via_relpath():
    from gpython import _is_buildout_script
    if _is_buildout_script(sys.executable):
        pytest.xfail("with buildout raw underlying interpreter does not have " +
                     "access to installed eggs")
    argv = ['-c',  'import sys; print(sys.version)']
    out1 = pyout(                    argv, pyexe=sys.executable)
    out2 = pyout(['./__init__.py'] + argv, pyexe=sys._gpy_underlying_executable, cwd=here)
    assert out1 == out2


# verify -X gpython.runtime=...
@gpython_only
def test_Xruntime(runtime):
    _xopt_assert_in_subprocess('gpython.runtime', runtime,
                                assert_gevent_activated  if runtime != 'threads'  else \
                                assert_gevent_not_activated)

# _xopt_assert_in_subprocess runs tfunc in subprocess interpreter spawned with
# `-X xopt=xval` and checks that there is no error.
#
# It is also verified that tfunc runs ok in sub-subprocess interpreter spawned
# _without_ `-X ...`, i.e. once given -X setting is inherited by spawned interpreters.
def _xopt_assert_in_subprocess(xopt, xval, tfunc):
    XOPT = xopt.upper().replace('.','_')    # gpython.runtime -> GPYTHON_RUNTIME
    env = os.environ.copy()
    env.pop(XOPT, None) # del

    argv = []
    if xval != '':
        argv += ['-X', xopt+'='+xval]
    prog = import_t = 'from gpython import gpython_test as t; '
    prog += 't.%s(); ' % tfunc.__name__
    prog += import_t  # + same in subprocess
    prog += "t.pyrun(['-c', '%s t.%s(); ']); " % (import_t, tfunc.__name__)
    prog += 'print("ok")'
    argv += ['-c', prog]

    out = pyout(argv, env=env)
    assert out == b'ok\n'


# ---- misc ----

# check_gpy_vs_py verifies that gpython output matches underlying python output.
def check_gpy_vs_py(argv, postprocessf=None, **kw):
        gpyout   = u(pyout(argv, **kw))
        stdpyout = u(pyout(argv, pyexe=sys._gpy_underlying_executable, **kw))
        gpyoutv   = gpyout.splitlines()
        stdpyoutv = stdpyout.splitlines()

        if postprocessf is not None:
            postprocessf(gpyoutv, stdpyoutv)

        assert gpyoutv == stdpyoutv

# _check_gpy_vs_py verifies that gpython stdout/stderr match underlying python stdout/stderr.
def _check_gpy_vs_py(argv, **kw):
    kw = kw.copy()
    kw['stdout'] = PIPE
    kw['stderr'] = PIPE
    gpyret, gpyout, gpyerr = _pyrun(argv, **kw)
    stdret, stdout, stderr = _pyrun(argv, pyexe=sys._gpy_underlying_executable, **kw)

    assert gpyout == stdout
    assert gpyerr == stderr
    assert (gpyret, stdret) == (0, 0)
