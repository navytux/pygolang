# -*- coding: utf-8 -*-
# Copyright (C) 2017-2019  Nexedi SA and Contributors.
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
"""Package testing mirrors Go testing package for things missed in Python"""

from __future__ import print_function, absolute_import

from time import time
from math import ceil, log10


# B is benchmarking timer/request passed to benchmarks as fixture
# similar to https://golang.org/pkg/testing/#B.
#
# Use benchmark to actually run a benchmark.
class B:
    # .N    number of iterations benchmarked function should do

    def __init__(self):
        self.N = 1              # preset to 1 iteration
        self._t_start = None    # t of timer started; None if timer is currently stopped
        self.reset_timer()

    def reset_timer(self):
        self._t_total = 0.

    def start_timer(self):
        if self._t_start is not None:
            return

        self._t_start = time()

    def stop_timer(self):
        if self._t_start is None:
            return

        t = time()
        self._t_total += t - self._t_start
        self._t_start = None

    def total_time(self):
        return self._t_total


# BenchmarkResult represent
class BenchmarkResult:
    # .N    number of iterations
    # .T    total time taken
    #
    # TODO memalloc stats
    def __init__(self, n, t):
        self.N, self.T = n, t


# _stopBenchmark, when returned by benchmarked function, tells benchmark driver
# to stop benchmarking this function.
#
# it is private since only py.bench uses it, and noone else should.
# (py.bench uses it to benchmark functions that do not take b as argument)
_stopBenchmark = object()

# benchmark benchmarks benchf auto-adjusting whole running time to ttarget.
#
# benchf is invoked as benchf(b).
def benchmark(benchf, ttarget = 1.):	# -> BenchmarkResult
    b = B()
    b.N = 0
    t = 0.
    while t < (ttarget * 0.9):
        if b.N == 0:
            b.N = 1
        else:
            n = b.N * (ttarget / t)     # exact how to adjust b.N to reach ttarget
            order = int(log10(n))       # n = k·10^order, k ∈ [1,10)
            k = float(n) / (10**order)
            k = ceil(k)                 # lift up k to nearest int
            b.N = int(k * 10**order)    # b.N = int([1,10))·10^order

        b.reset_timer()
        b.start_timer()
        x = benchf(b)
        b.stop_timer()
        t = b.total_time()

        # stop trying to reach ttarget if benchf asks us so.
        if x is _stopBenchmark:
            break

    return BenchmarkResult(b.N, t)
