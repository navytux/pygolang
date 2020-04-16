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
"""_runtime_gevent.pyx provides libgolang runtime based on gevent greenlets."""

from __future__ import print_function, absolute_import

# Gevent runtime uses gevent's greenlets and semaphores.
# When sema.acquire() blocks, gevent switches us from current to another greenlet.

# gevent >= 1.5 stopped to provide pxd to its API
# https://github.com/gevent/gevent/issues/1568
#
# on pypy gevent does not compile greenlet.py and semaphore.py citing that
# "there is no greenlet.h on pypy"
IF (GEVENT_VERSION_HEX < 0x01050000) and (not PYPY):
    from gevent._greenlet cimport Greenlet
    from gevent.__semaphore cimport Semaphore
    ctypedef Semaphore PYGSema
ELSE:
    from gevent.greenlet import Greenlet
    from gevent._semaphore import Semaphore
    ctypedef object PYGSema

from gevent import sleep as pygsleep

from libc.stdint cimport uint64_t
from cpython cimport Py_INCREF, Py_DECREF
from cython cimport final

from golang.runtime._libgolang cimport _libgolang_runtime_ops, _libgolang_sema, \
        STACK_DEAD_WHILE_PARKED, panic
from golang.runtime cimport _runtime_thread
from golang.runtime._runtime_pymisc cimport PyExc, pyexc_fetch, pyexc_restore


# _goviapy & _togo serve go
def _goviapy(_togo _ not None):
    with nogil:
        _.f(_.arg)

@final
cdef class _togo:
    cdef void (*f)(void *) nogil
    cdef void *arg


# internal functions that work under gil
cdef:
    # XXX better panic with pyexc object and detect that at recover side?

    bint _go(void (*f)(void *) nogil, void *arg):
        _ = _togo(); _.f = f; _.arg = arg
        g = Greenlet(_goviapy, _)
        g.start()
        return True

    _libgolang_sema* _sema_alloc():
        pygsema = Semaphore()
        Py_INCREF(pygsema)
        return <_libgolang_sema*>pygsema

    bint _sema_free(_libgolang_sema *gsema):
        pygsema = <PYGSema>gsema
        Py_DECREF(pygsema)
        return True

    bint _sema_acquire(_libgolang_sema *gsema):
        pygsema = <PYGSema>gsema
        pygsema.acquire()
        return True

    bint _sema_release(_libgolang_sema *gsema):
        pygsema = <PYGSema>gsema
        pygsema.release()
        return True

    bint _nanosleep(uint64_t dt):
        cdef double dt_s = dt * 1E-9
        pygsleep(dt_s)
        return True


# nogil runtime API
cdef nogil:

    void go(void (*f)(void *), void *arg):
        cdef PyExc exc
        with gil:
            pyexc_fetch(&exc)
            ok = _go(f, arg)
            pyexc_restore(exc)
        if not ok:
            panic("pyxgo: gevent: go: failed")

    _libgolang_sema* sema_alloc():
        cdef PyExc exc
        with gil:
            pyexc_fetch(&exc)
            sema = _sema_alloc()
            pyexc_restore(exc)
        return sema # libgolang checks for NULL return

    void sema_free(_libgolang_sema *gsema):
        cdef PyExc exc
        with gil:
            pyexc_fetch(&exc)
            ok = _sema_free(gsema)
            pyexc_restore(exc)
        if not ok:
            panic("pyxgo: gevent: sema: free: failed")

    void sema_acquire(_libgolang_sema *gsema):
        cdef PyExc exc
        with gil:
            pyexc_fetch(&exc)
            ok = _sema_acquire(gsema)
            pyexc_restore(exc)
        if not ok:
            panic("pyxgo: gevent: sema: acquire: failed")

    void sema_release(_libgolang_sema *gsema):
        cdef PyExc exc
        with gil:
            pyexc_fetch(&exc)
            ok = _sema_release(gsema)
            pyexc_restore(exc)
        if not ok:
            panic("pyxgo: gevent: sema: release: failed")

    void nanosleep(uint64_t dt):
        cdef PyExc exc
        with gil:
            pyexc_fetch(&exc)
            ok = _nanosleep(dt)
            pyexc_restore(exc)
        if not ok:
            panic("pyxgo: gevent: sleep: failed")


    # XXX const
    _libgolang_runtime_ops gevent_ops = _libgolang_runtime_ops(
            # when greenlet is switched to another, its stack is copied to
            # heap, and stack of switched-to greenlet is copied back to C stack.
            flags           = STACK_DEAD_WHILE_PARKED,

            go              = go,
            sema_alloc      = sema_alloc,
            sema_free       = sema_free,
            sema_acquire    = sema_acquire,
            sema_release    = sema_release,
            nanosleep       = nanosleep,
            nanotime        = _runtime_thread.nanotime, # reuse from _runtime_thread
    )

from cpython cimport PyCapsule_New
libgolang_runtime_ops = PyCapsule_New(&gevent_ops,
        "golang.runtime._runtime_gevent.libgolang_runtime_ops", NULL)
