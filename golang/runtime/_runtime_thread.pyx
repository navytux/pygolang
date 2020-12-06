# cython: language_level=2
# Copyright (C) 2019-2020  Nexedi SA and Contributors.
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
"""_runtime_thread.pyx provides libgolang runtime based on OS threads."""

from __future__ import print_function, absolute_import

# Thread runtime reuses C-level Python threadcreate + semaphore implementation
# for portability. In Python semaphores do not depend on GIL and by reusing
# the implementation we can offload us from covering different systems.
#
# On POSIX, for example, Python uses sem_init(process-private) + sem_post/sem_wait.
#
# Similarly PyThread_start_new_thread - Python's C function function to create
# new thread - does not depend on GIL. On POSIX, for example, it is small
# wrapper around pthread_create.
#
# NOTE Cython declares PyThread_acquire_lock/PyThread_release_lock as nogil
from cpython.pythread cimport PyThread_acquire_lock, PyThread_release_lock, \
        PyThread_type_lock, WAIT_LOCK

# NOTE On Darwin, even though this is considered as POSIX, Python uses
# mutex+condition variable to implement its lock, and, as of 20190828, Py2.7
# implementation, even though similar issue was fixed for Py3 in 2012, contains
# synchronization bug: the condition is signalled after mutex unlock while the
# correct protocol is to signal condition from under mutex:
#
#   https://github.com/python/cpython/blob/v2.7.16-127-g0229b56d8c0/Python/thread_pthread.h#L486-L506
#   https://github.com/python/cpython/commit/187aa545165d (py3 fix)
#
# PyPy has the same bug for both pypy2 and pypy3:
#
#   https://foss.heptapod.net/pypy/pypy/-/blob/ab03445c3b48/rpython/translator/c/src/thread_pthread.c#L443-465
#   https://foss.heptapod.net/pypy/pypy/-/blob/release-pypy3.5-v7.0.0/rpython/translator/c/src/thread_pthread.c#L443-465
#
# This way when Pygolang is used with buggy Python/darwin, the bug leads to
# frequently appearing deadlocks, while e.g. CPython3/darwin works ok.
#
# The bug was reported to CPython/PyPy upstreams:
#
# - https://bugs.python.org/issue38106
# - https://foss.heptapod.net/pypy/pypy/-/issues/3072
#
# and fixed in CPython 2.7.17 and PyPy 7.2 .
import sys, platform
if 'darwin' in sys.platform:
    pyimpl = platform.python_implementation()
    pyver  = sys.version_info
    buggy  = buglink = None
    if 'CPython' in pyimpl and pyver < (3, 0) and pyver < (2,7,17):
        buggy   = "cpython2/darwin < 2.7.17"
        buglink = "https://bugs.python.org/issue38106"
    if 'PyPy' in pyimpl and sys.pypy_version_info < (7,2):
        buggy   = "pypy/darwin < 7.2"
        buglink = "https://foss.heptapod.net/pypy/pypy/-/issues/3072"
    if buggy:
        print("WARNING: pyxgo: thread: %s has race condition bug in runtime"
              " that leads to deadlocks (%s)" % (buggy, buglink), file=sys.stderr)

# make sure python threading is initialized, so that there is no concurrent
# calls to PyThread_init_thread from e.g. PyThread_allocate_lock later.
#
# This allows us to treat PyThread_allocate_lock & PyThread_start_new_thread as nogil.
from cpython.ceval cimport PyEval_InitThreads
#PyThread_init_thread()     # initializes only threading, but _not_ GIL
PyEval_InitThreads()        # initializes      threading       and  GIL
cdef extern from "pythread.h" nogil:
    # NOTE py3.7 changed to `unsigned long PyThread_start_new_thread ...`
    long PyThread_start_new_thread(void (*)(void *), void *)
    PyThread_type_lock PyThread_allocate_lock()
    void PyThread_free_lock(PyThread_type_lock)

from golang.runtime._libgolang cimport _libgolang_runtime_ops, _libgolang_sema, \
        _libgolang_runtime_flags, panic

from libc.stdint cimport uint64_t, UINT64_MAX
IF POSIX:
    from posix.time cimport clock_gettime, nanosleep as posix_nanosleep, timespec, CLOCK_REALTIME
    from libc.errno cimport errno, EINTR
ELSE:
    # !posix via-gil timing fallback
    import time as pytimemod
    from golang.runtime._runtime_pymisc cimport PyExc, pyexc_fetch, pyexc_restore

    cdef:
        bint _nanosleep(double dt_s):
            pytimemod.sleep(dt_s)
            return True

        (double, bint) _nanotime():
            cdef double t_s
            t_s = pytimemod.time()
            return t_s, True


DEF i1E9 = 1000000000
#           987654321

cdef nogil:

    void go(void (*f)(void *), void *arg):
        pytid = PyThread_start_new_thread(f, arg)
        if pytid == -1:
            panic("pygo: failed")

    _libgolang_sema* sema_alloc():
        # python calls it "lock", but it is actually a semaphore.
        # and in particular can be released by thread different from thread that acquired it.
        pysema = PyThread_allocate_lock()
        return <_libgolang_sema *>pysema # NULL is ok - libgolang expects it

    void sema_free(_libgolang_sema *gsema):
        pysema = <PyThread_type_lock>gsema
        PyThread_free_lock(pysema)

    void sema_acquire(_libgolang_sema *gsema):
        pysema = <PyThread_type_lock>gsema
        ok = PyThread_acquire_lock(pysema, WAIT_LOCK)
        if ok == 0:
            panic("pyxgo: thread: sema_acquire: PyThread_acquire_lock failed")

    void sema_release(_libgolang_sema *gsema):
        pysema = <PyThread_type_lock>gsema
        PyThread_release_lock(pysema)

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
        void nanosleep(uint64_t dt):
            cdef double dt_s = dt * 1E-9 # no overflow possible
            cdef PyExc exc
            with gil:
                pyexc_fetch(&exc)
                ok = _nanosleep(dt_s)
                pyexc_restore(exc)
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
        uint64_t nanotime():
            cdef double t_s
            cdef PyExc exc
            with gil:
                pyexc_fetch(&exc)
                t_s, ok = _nanotime()
                pyexc_restore(exc)
            if not ok:
                panic("pyxgo: thread: nanotime: pytime.time failed")
            t_ns = t_s * 1E9
            if t_ns > UINT64_MAX:
                panic("pyxgo: thread: nanotime: time overflow")
            return <uint64_t>t_ns


    # XXX const
    _libgolang_runtime_ops thread_ops = _libgolang_runtime_ops(
            flags           = <_libgolang_runtime_flags>0,
            go              = go,
            sema_alloc      = sema_alloc,
            sema_free       = sema_free,
            sema_acquire    = sema_acquire,
            sema_release    = sema_release,
            nanosleep       = nanosleep,
            nanotime        = nanotime,
    )

from cpython cimport PyCapsule_New
libgolang_runtime_ops = PyCapsule_New(&thread_ops,
        "golang.runtime._runtime_thread.libgolang_runtime_ops", NULL)
