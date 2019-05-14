#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2014-2019  Nexedi SA and Contributors.
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
"""Program py.bench benchmarks python code via py.test .

py.bench, similarly to py.test, discovers bench_* functions and Bench* classes
and then runs each discovered benchmark via golang.testing.benchmark. Similarly
to `go test -bench`, benchmarking results are printed in Go benchmark format.

For example, running py.bench on the following code::

    def bench_add(b):
        x, y = 1, 2
        for i in xrange(b.N):
            x + y

gives something like::

    $ py.bench --count=3 x.py
    ...
    pymod: bench_add.py
    Benchmarkadd    50000000        0.020 µs/op
    Benchmarkadd    50000000        0.020 µs/op
    Benchmarkadd    50000000        0.020 µs/op
"""

from __future__ import print_function, absolute_import

import sys

# don't force pytest dependency on whole golang
try:
    import pytest
except ImportError:
    print("E: py.bench: cannot work: py.test not found - please install pytest egg", file=sys.stderr)
    sys.exit(1)

import _pytest.runner
from _pytest.terminal import TerminalReporter as _pytest_TerminalReporter
from py.process import ForkedFunc

from golang import testing

from six.moves import range as xrange

# XXX hack for ForkedFunc not to capture stdout/stderr.
#     so that test prints could be seen when run under --capture=no
#     otoh, py.test captures stdout/stderr fds so here we don't have to.
import py._process.forkedfunc
class XForkedFunc(ForkedFunc):

    def _child(self, nice, on_start, on_exit):
        # we are monkeypatching only in child, so no effect on parent =safe
        py._process.forkedfunc.get_unbuffered_io = self._fake_get_unbuffered_io

        return ForkedFunc._child(self, nice, on_start, on_exit)

    @staticmethod
    def _fake_get_unbuffered_io(fd, _):
        if fd == 1: return sys.stdout
        if fd == 2: return sys.stderr
        raise RuntimeError("only stdout/stderr expected")



# BenchPlugin is py.test plugin to collect & run benchmarks.
class BenchPlugin:

    # redirect python collector to bench_*.py and bench_*()
    def pytest_configure(self, config):
        # XXX a bit hacky
        ini = config.inicfg
        ini['python_files']     = 'bench_*.py'
        ini['python_classes']   = 'Bench'
        ini['python_functions'] = 'bench_'
        config._inicache.clear()


    def pytest_addoption(self, parser):
        g = parser.getgroup('benchmarking')
        g.addoption('--count',  action='store', type=int, dest='benchcount', default=1,
                    help="number of time to run each benchmark")
        g.addoption('--forked', action='store_true',      dest='forked', default=False,
                    help="run each benchmark in separate process")


    # b fixture makes benchmarking B be available as `b` func arg.
    @pytest.fixture(scope="function")
    def b(self, request):
        """Provides access to benchmarking timer"""
        # NOTE here request is subrequest of item._request in pytest_runtest_setup
        request._parent_request._bench_b_used = True
        return None # we don't have b here - it will be overwritten by pytest_runtest_call.run

    # run a benchmark `benchcount` times.
    def pytest_runtest_call(self, item):
        # run benchmarks item.runtest via testing.benchmark.
        def run():
            def _(b):
                b.stop_timer()
                b_used = getattr(item._request, '_bench_b_used', False)
                if b_used:
                    bfixdef = item._request._fixture_defs['b']
                    bfixdef.cached_result = (b,) + bfixdef.cached_result[1:]
                    assert item._request.getfixturevalue('b') is b

                    # re-sync the fixture in item, as this can be already filled with old b value
                    item.funcargs.pop('b', None)
                    item._request._fillfixtures()
                    assert item.funcargs['b'] is b
                b.start_timer()

                item.runtest()

                # break if func does not accept b as arg
                # (i.e. it will do only 1 its full iteration)
                if not b_used:
                    return testing._stopBenchmark

            r = testing.benchmark(_)
            # NOTE cannot return r directly - ForkedFunc uses marshal which cannot handle objects
            return (r.N, r.T)

        rv = []
        for i in xrange(item.config.option.benchcount):
            if not item.config.option.forked:
                r = run()

            else:
                # run in separate process.
                runf = XForkedFunc(run)
                result = runf.waitfinish()
                if result.exitstatus == XForkedFunc.EXITSTATUS_EXCEPTION:
                    print(result.err, file=sys.stderr)  # XXX vs runf doesn't capture stderr
                    1/0 # TODO re-raise properly
                elif result.exitstatus != 0:
                    print(result.err, file=sys.stderr)  # XXX vs runf doesn't capture stderr
                    1/0 # TODO handle properly

                r = result.retval

            rv.append(r)
        #print ('RET', rv)
        return rv


    # set benchmarking time in report, if run ok
    def pytest_runtest_makereport(self, item, call):
        report = _pytest.runner.pytest_runtest_makereport(item, call)
        if call.when == 'call' and not call.excinfo:
            # in pytest3 there is no way to mark pytest_runtest_call as 'firstresult'
            # let's emulate firstresult logic here
            assert len(call.result) == 1
            report.bench_resv = call.result[0]
        return report


# XXX hack: prevent std pytest runner from executing bench items.
# if we don't, _pytest.runner, besides runs performed by BenchPlugin, will also
# try to run benchmarks by itself, which:
# - can take additional time,
# - does not work with b from-inside hooking logic we do in BenchPlugin.
#
# XXX the reason we have to disable it in hacky way is that pytest3 does not
# allow pytest_runtest_call to be marked as firstresult=True.
_pytest.runner.pytest_runtest_call = lambda item: None


# colors to use when printing !passed
# XXX somewhat dup from _pytest/terminal.py
def report_markup(report):
    m = {}
    if report.failed:
        m = {'red': True, 'bold': True}
    elif report.skipeed:
        m = {'yellow': True}
    return m


# max(seq) or 0 if !seq
def max0(seq):
    seq = list(seq) # if generator -> generate
    if not seq:
        return 0
    else:
        return max(seq)

# benchname(nodeid) returns name of a benchmark from a function nodeid
def benchname(nodeid):
    pyname = nodeid.split("::", 1)[1] # everything after fspath
    # replace 'bench_' with 'Benchmark' prefix so that benchmark output matches
    # golang format
    if pyname.startswith('bench_'):
        pyname = pyname[len('bench_'):]
    return 'Benchmark' + pyname

# Adjusted terminal reporting to benchmarking needs
class XTerminalReporter(_pytest_TerminalReporter):

    # determine largest item name (to ralign timings)
    def pytest_collection_finish(self, session):
        _pytest_TerminalReporter.pytest_collection_finish(self, session)

        self.benchname_maxlen = max0(len(benchname(_.nodeid)) for _ in session.items)


    def pytest_runtest_logstart(self, nodeid, location):
        # print `pymod: ...` header for every module
        fspath = self.config.rootdir.join(nodeid.split("::")[0])
        if fspath == self.currentfspath:
            return
        first = (self.currentfspath == None)
        self.currentfspath = fspath
        fspath = self.startdir.bestrelpath(fspath)
        self._tw.line()
        # vskip in between modules
        if not first:
            self._tw.line()
        self.write("pymod: %s" % fspath)

    def pytest_runtest_logreport(self, report):
        _ =self.config.hook.pytest_report_teststatus(report=report)
        cat, letter, word = _
        self.stats.setdefault(cat, []).append(report)  # XXX needed for bench?
        if not letter and not word:
            # passed setup/teardown
            return

        def printname():
            self._tw.line()
            self._tw.write('%-*s\t' % (self.benchname_maxlen, benchname(report.nodeid)))

        if not report.passed:
            printname()
            self._tw.write('[%s]' % word, **report_markup(report))
            return

        # TODO ralign timing
        for niter, t in report.bench_resv:
            printname()
            self._tw.write('%d\t%.3f µs/op' % (niter, t * 1E6 / niter))


# there is no way to override it otherwise - it is hardcoded in
# _pytest.terminal's pytest_configure()
_pytest.terminal.TerminalReporter = XTerminalReporter


def main():
    pytest.main(plugins=[BenchPlugin()])


if __name__ == '__main__':
    main()
