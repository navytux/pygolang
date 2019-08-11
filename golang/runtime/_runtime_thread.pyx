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
"""_runtime_thread.pyx provides libgolang runtime based on OS threads"""

from __future__ import print_function, absolute_import

# Thread runtime reuses C-level Python threadcreate + semaphore implementation
# for portability. In Python semaphores do not depend on GIL and by reusing
# the implementation we can offload us from covering different systems.
#
# On POSIX, for example, Python uses sem_init(process-private) + sem_post/sem_wait.
# NOTE Cython declares PyThread_acquire_lock/PyThread_release_lock as nogil
#
# Similarly PyThread_start_new_thread - Python's C function function to create
# new thread - does not depend on GIL. On POSIX, for example, it is small
# wrapper around pthread_create.
#
# XXX review text
from cpython.pythread cimport PyThread_acquire_lock, PyThread_release_lock, WAIT_LOCK, \
        PyThread_type_lock

# make sure python threading is initialized, so that there is no concurrent
# calls to PyThread_init_thread from e.g. PyThread_allocate_lock later.
#
# This allows us to treat PyThread_allocate_lock & PyThread_start_new_thread as nogil.
from cpython.ceval cimport PyEval_InitThreads
#PyThread_init_thread()     # initializes only threading, but _not_ GIL
PyEval_InitThreads()        # initializes      threading       and  GIL
cdef extern from "pythread.h" nogil:
    long PyThread_start_new_thread(void (*)(void *), void *)
    PyThread_type_lock PyThread_allocate_lock()
    void PyThread_free_lock(PyThread_type_lock)

from golang.runtime._libgolang cimport _libgolang_runtime_ops, _libgolang_sema, \
        _libgolang_runtime_flags, panic

from libc.stdint cimport uint64_t
# for !posix nanosleep fallback
import time as pytimemod


cdef nogil:

    void go(void (*f)(void *), void *arg):
        cdef long pythreadid # NOTE py3.7 changed to unsigned long
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
        PyThread_acquire_lock(pysema, WAIT_LOCK)

    void sema_release(_libgolang_sema *gsema):
        pysema = <PyThread_type_lock>gsema
        PyThread_release_lock(pysema)

    void nanosleep(uint64_t dt):
        # XXX POSIX -> nanosleep syscall
        cdef double dt_s = dt * 1E-9
        with gil:
            print('pytimemod.sleep', dt_s)
            pytimemod.sleep(dt_s)

    uint64_t nanotime():
        # XXX POSIX -> ... syscall
        cdef double t_s
        with gil:
            t_s = pytimemod.time()  # XXX pyexc -> panic
        # XXX check for overflow -> panic?
        return <uint64_t>(t_s * 1E9)


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
