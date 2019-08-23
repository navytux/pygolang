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
"""_runtime_thread.pyx provides libgolang runtime based on OS threads."""

from __future__ import print_function, absolute_import

from golang.runtime._libgolang cimport _libgolang_runtime_ops, panic

from libc.stdint cimport uint64_t, UINT64_MAX
IF POSIX:
    from posix.time cimport clock_gettime, nanosleep as posix_nanosleep, timespec, CLOCK_REALTIME
    from libc.errno cimport errno, EINTR
ELSE:
    # for !posix timing fallback
    import time as pytimemod

DEF i1E9 = 1000000000
#           987654321

cdef nogil:

    IF POSIX:
        void nanosleep(uint64_t dt):
            cdef timespec ts
            ts.tv_sec  = dt // i1E9
            ts.tv_nsec = dt  % i1E9
            err = posix_nanosleep(&ts, NULL)
            if err == -1 and errno == EINTR:
                err = 0 # XXX ok?
            if err == -1:
                panic("pyxgo: thread: nanosleep: nanosleep failed") # XXX +errno
    ELSE:
        bint _nanosleep(uint64_t dt):
            cdef double dt_s = dt * 1E-9 # no overflow possible
            with gil:
                pytimemod.sleep(dt_s)
                return True
        void nanosleep(uint64_t dt):
            ok = _nanosleep(dt)
            if not ok:
                panic("pyxgo: thread: nanosleep: pytime.sleep failed")

    IF POSIX:
        uint64_t nanotime():
            cdef timespec ts
            cdef int err = clock_gettime(CLOCK_REALTIME, &ts)
            if err == -1:
                panic("pyxgo: thread: nanotime: clock_gettime failed") # XXX +errno
            if not (0 <= ts.tv_sec and (0 <= ts.tv_nsec <= i1E9)):
                panic("pyxgo: thread: nanotime: clock_gettime -> invalid")
            if ts.tv_sec > (UINT64_MAX / i1E9 - 1):
                panic("pyxgo: thread: nanotime: clock_gettime -> overflow")
            return ts.tv_sec*i1E9 + ts.tv_nsec
    ELSE:
        (uint64_t, bint) _nanotime():
            cdef double t_s
            with gil:
                t_s = pytimemod.time()
            t_ns = t_s * 1E9
            if t_ns > UINT64_MAX:
                panic("pyxgo: thread: nanotime: time overflow")
            return <uint64_t>t_ns, True
        uint64_t nanotime():
            t, ok = _nanotime()
            if not ok:
                panic("pyxgo: thread: nanotime: pytime.time failed")
            return t


    # XXX const
    _libgolang_runtime_ops thread_ops = _libgolang_runtime_ops(
            nanosleep       = nanosleep,
            nanotime        = nanotime,
    )

from cpython cimport PyCapsule_New
libgolang_runtime_ops = PyCapsule_New(&thread_ops,
        "golang.runtime._runtime_thread.libgolang_runtime_ops", NULL)
