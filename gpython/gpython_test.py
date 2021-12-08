# -*- coding: utf-8 -*-
# Copyright (C) 2019-2021  Nexedi SA and Contributors.
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

    # indirectly verify golang.__all__
    for k in golang.__all__:
        assert getattr(builtins, k) is getattr(golang, k)

@gpython_only
def test_gevent_activated():
    # gpython, by default, acticates gevent.
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
    assert _ == b"hello\nworld\n['%s', 'abc', 'def']\n" % b(hellopy)
    # -m<module>
    __ = pyout(['-mhello', 'abc', 'def'], cwd=testdata)
    assert __ == _

    # file
    _ = pyout(['testdata/hello.py', 'abc', 'def'], cwd=here)
    assert _ == b"hello\nworld\n['testdata/hello.py', 'abc', 'def']\n"

    # -i after stdin (also tests interactive mode as -i forces interactive even on non-tty)
    d = {
        b'hellopy': b(hellopy),
        b'ps1':     b'' # cpython emits prompt to stderr
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
    # -i after -m
    _ = pyout(['-i', '-m', 'hello'], stdin=b'world.tag', cwd=testdata)
    assert _ == b"hello\nworld\n['%(hellopy)s']\n%(ps1)s'~~WORLD~~'\n%(ps1)s"  % d
    # -i after file
    _ = pyout(['-i', 'testdata/hello.py'], stdin=b'tag', cwd=here)
    assert _ == b"hello\nworld\n['testdata/hello.py']\n%(ps1)s'~~HELLO~~'\n%(ps1)s" % d


    # -W <opt>
    _ = pyout(['-Werror', '-Whello', '-W', 'ignore::DeprecationWarning',
               'testprog/print_warnings_setup.py'], cwd=here)
    if PY2:
        # py2 threading, which is imported after gpython startup, adds ignore
        # for sys.exc_clear
        _ = grepv(r'ignore:sys.exc_clear:DeprecationWarning:threading:*', _)
    assert _.startswith(
        b"sys.warnoptions: ['error', 'hello', 'ignore::DeprecationWarning']\n\n" + \
        b"warnings.filters:\n" + \
        b"- ignore::DeprecationWarning::*\n" + \
        b"- error::Warning::*\n"), _
    # $PYTHONWARNINGS
    _ = pyout(['testprog/print_warnings_setup.py'], cwd=here,
              envadj={'PYTHONWARNINGS': 'ignore,world,error::SyntaxWarning'})
    if PY2:
        # see ^^^
        _ = grepv(r'ignore:sys.exc_clear:DeprecationWarning:threading:*', _)
    assert _.startswith(
        b"sys.warnoptions: ['ignore', 'world', 'error::SyntaxWarning']\n\n" + \
        b"warnings.filters:\n" + \
        b"- error::SyntaxWarning::*\n" + \
        b"- ignore::Warning::*\n"), _


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


# verify thay pymain runs programs with __main__ module correctly setup.
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

        check_gpy_vs_py(argv, postprocessf=_, **kw)

    check([], stdin=b'import print_syspath', cwd=testprog,  # stdin
            path0realpath2cwd=(PY3 and is_pypy)) # https://foss.heptapod.net/pypy/pypy/-/issues/3610
    check(['-c', 'import print_syspath'], cwd=testprog)     # -c
    check(['-m', 'print_syspath'], cwd=testprog,            # -m
            path0cwd2realpath=PY2)
    check(['testprog/print_syspath.py'], cwd=here)          # file


# verify that pymain handles -O in exactly the same was as underlying python does.
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
    env = os.environ.copy()
    env.pop('GPYTHON_RUNTIME', None) # del

    argv = []
    if runtime != '':
        argv += ['-X', 'gpython.runtime='+runtime]
    prog = 'from gpython import gpython_test as t; '
    if runtime != 'threads':
        prog += 't.assert_gevent_activated(); '
    else:
        prog += 't.assert_gevent_not_activated(); '
    prog += 'print("ok")'
    argv += ['-c', prog]

    out = pyout(argv, env=env)
    assert out == b'ok\n'


# ---- misc ----

# grepv filters out lines matching pattern from text.
def grepv(pattern, text): # -> text
    if isinstance(text, bytes):
        t = b''
    else:
        t = ''
    p = re.compile(pattern)
    v = []
    for l in text.splitlines(True):
        m = p.search(l)
        if not m:
            v.append(l)
    return t.join(v)

# check_gpy_vs_py verifies that gpython output matches underlying python output.
def check_gpy_vs_py(argv, postprocessf=None, **kw):
        gpyout   = u(pyout(argv, **kw))
        stdpyout = u(pyout(argv, pyexe=sys._gpy_underlying_executable, **kw))
        gpyoutv   = gpyout.splitlines()
        stdpyoutv = stdpyout.splitlines()

        if postprocessf is not None:
            postprocessf(gpyoutv, stdpyoutv)

        assert gpyoutv == stdpyoutv
