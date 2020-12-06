# -*- coding: utf-8 -*-
# cython: language_level=2
# distutils: language=c++
#
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

# small tests that verifies pyx-level sync API.
# the work of sync package itself is exercised thoroughly mostly in sync_test.py

from __future__ import print_function, absolute_import

from golang cimport go, chan, makechan, structZ, nil, panic, topyexc
from golang cimport sync, time

# C-level _sema + _mutex
# (not exposed in sync.pxd as it exposes only high-level API)
cdef extern from "golang/sync.h" namespace "golang::sync" nogil:
    """
    namespace golang {
    namespace sync {
        void _mutex_init(sync::Mutex *mu) {
            new (mu) sync::Mutex();
        }
        void _mutex_destroy(sync::Mutex *mu) {
            mu->~Mutex();
        }
    }}  // golang::sync::
    """
    struct _sema
    _sema *_makesema()
    void _semafree(_sema *)
    void _semaacquire(_sema *)
    void _semarelease(_sema *)

    void _mutex_init(sync.Mutex *)
    void _mutex_destroy(sync.Mutex *)

from libc.stdlib cimport calloc, free
from libc.stdio cimport printf


# test for semaphore wakeup, when wakeup is done not by the same thread which
# did the original acquire. This used to corrupt memory and deadlock on macOS
# due to CPython & PyPy runtime bugs:
#   https://bugs.python.org/issue38106
#   https://foss.heptapod.net/pypy/pypy/-/issues/3072
cdef nogil:
    struct WorkState:
        sync.Mutex mu       # protects vvv
        _sema      *sema    # T1 <- T2 wakeup; reallocated on every iteration
        bint stop           # T1 -> T2: request to stop
        chan[structZ] done  # T1 <- T2: stopped

    void _test_sema_wakeup_T2(void *_state):
        state = <WorkState*>_state
        cdef int i = 0, j
        cdef bint stop
        cdef double Wstart, now
        while 1:
            i += 1
            # wait till .sema != nil and pop it
            Wstart = time.now()
            j = 0
            while 1:
                state.mu.lock()
                sema = state.sema
                if sema != nil:
                    state.sema = NULL
                stop = state.stop
                state.mu.unlock()

                if stop:
                    state.done.close()
                    return
                if sema != nil:
                    break

                now = time.now()
                if (now - Wstart) > 3*time.second:
                    printf("\nSTUCK on iteration #%d\n", i)
                    panic("STUCK")

                # workaround for "gevent" runtime: yield CPU so that T1 can run
                # XXX better yield always for "gevent", don't yield at all for "thread"
                j += 1
                if (j % 100) == 0:
                    time.sleep(0)

            # we have popped .sema from state. This means that peer is _likely_ waiting on it
            _semarelease(sema)  # either release or release + wakeup in-progress acquire


    void _test_sema_wakeup() except +topyexc:
        cdef WorkState *state = <WorkState *>calloc(1, sizeof(WorkState))
        if state == nil:
            panic("malloc -> nil")
        state.sema = NULL
        _mutex_init(&state.mu)
        state.stop = False
        state.done = makechan[structZ]()

        go(_test_sema_wakeup_T2, state)

        N = 100000
        cdef _sema *sema_prev = NULL
        for i in range(N):
            sema = _makesema()
            _semaacquire(sema)

            #printf("d(sema_prev, sema): %ld\n", <char*>sema - <char*>sema_prev)

            state.mu.lock()
            state.sema = sema
            state.mu.unlock()

            _semaacquire(sema)
            # _semarelease(sema) # (to free sema in released state)
            #                    # (gets stuck both with and without it)
            _semafree(sema)
            sema_prev = sema

        state.mu.lock()
        state.stop = True
        state.mu.unlock()

        state.done.recv()
        state.done = nil
        _mutex_destroy(&state.mu)
        free(state)

def test_sema_wakeup():
    with nogil:
        _test_sema_wakeup()


# verify Once
cdef nogil:
    int  _once_ncall = 0
    void _once_call():
        global _once_ncall
        _once_ncall += 1

cdef void _test_once() nogil except +topyexc:
    cdef sync.Once once
    if not (_once_ncall == 0):
        panic("once @0: ncall != 0")
    once.do(_once_call);
    if not (_once_ncall == 1):
        panic("once @1: ncall != 1")
    once.do(_once_call);
    if not (_once_ncall == 1):
        panic("once @2: ncall != 1")
    once.do(_once_call);
    if not (_once_ncall == 1):
        panic("once @3: ncall != 1")

def test_once():
    with nogil:
        _test_once()


# sync_test.cpp
cdef extern from * nogil:
    """
    extern void _test_sync_once_cpp();
    """
    void _test_sync_once_cpp()                  except +topyexc
def test_sync_once_cpp():
    with nogil:
        _test_sync_once_cpp()
