# cython: language_level=2
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

# Tests for pyx/runtime.pyx + libpyxruntime.

from __future__ import print_function, absolute_import

from golang cimport go, chan, makechan, structZ, select, panic
from golang cimport time
from golang.pyx cimport runtime

from cpython cimport PyObject
from libc.stdio cimport printf


ctypedef chan[structZ] chanZ
cdef structZ Z

# verify that there is no deadlock in libpyxruntime.pygil_ensure():
# it used to lock pyexitedMu -> GIL, which if also called with GIL initially
# held leads to deadlocks in AB BA scenario.
def test_pyfunc_vs_gil_deadlock():
    def f():
        time.sleep(0.001*time.second) # NOTE nogil sleep, _without_ releasing gil

    with nogil:
        _test_pyfunc_vs_gil_deadlock(runtime.PyFunc(<PyObject*>f))

cdef void _test_pyfunc_vs_gil_deadlock(runtime.PyFunc pyf) nogil:
    N = 100

    cdef chanZ ready = makechan[structZ]() # main <- spawned       "I'm ready"
    cdef chanZ start = makechan[structZ]() # main -> all spawned   "Start running"
    cdef chanZ done  = makechan[structZ]() # main <- spawned       "I'm finished"
    go(_runGM, N, pyf, ready, start, done)
    go(_runMG, N, pyf, ready, start, done)
    ready.recv(); ready.recv()
    start.close()

    cdef int ndone = 0
    timeoutq = time.after(5*time.second)
    while 1:
        _ = select([
            done.recvs(),       # 0
            timeoutq.recvs(),   # 1
        ])
        if _ == 0:
            ndone += 1
            if ndone == 2:
                break   # all ok
        if _ == 1:
            printf("\nSTUCK\n")
            panic("STUCK")

cdef nogil:

    # run in a loop locking GIL -> pyexitMu
    void _runGM(int n, runtime.PyFunc pyf, chanZ ready, chanZ start, chanZ done):
        ready.send(Z)
        start.recv()
        for i in range(n):
            #printf("GM %d\n", i)
            with gil:
                pyf()
        done.send(Z)

    # run in a loop locking pyexitMu -> GIL
    void _runMG(int n, runtime.PyFunc pyf, chanZ ready, chanZ start, chanZ done):
        ready.send(Z)
        start.recv()
        for i in range(n):
            #printf("MG %d\n", i)
            # already in nogil
            pyf()
        done.send(Z)
