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
"""_sync.pyx implements sync.pyx - see _sync.pxd for package overview."""

from __future__ import print_function, absolute_import

from cython  cimport final
from cpython cimport PyObject
from golang  cimport topyexc

@final
cdef class PySema:
    cdef Sema sema

    # FIXME cannot catch/pyreraise panic of .sema ctor
    # https://github.com/cython/cython/issues/3165

    def acquire(PySema pysema):
        with nogil:
            semaacquire_pyexc(&pysema.sema)

    def release(PySema pysema):
        semarelease_pyexc(&pysema.sema)

    # with support
    __enter__ = acquire
    def __exit__(pysema, exc_typ, exc_val, exc_tb):
        pysema.release()

@final
cdef class PyMutex:
    cdef Mutex mu

    # FIXME cannot catch/pyreraise panic of .mu ctor
    # https://github.com/cython/cython/issues/3165

    def lock(PyMutex pymu):
        with nogil:
            mutexlock_pyexc(&pymu.mu)

    def unlock(PyMutex pymu):
        mutexunlock_pyexc(&pymu.mu)


    # with support
    __enter__ = lock
    def __exit__(PyMutex pymu, exc_typ, exc_val, exc_tb):
        pymu.unlock()


@final
cdef class PyOnce:
    """Once allows to execute an action only once.

    For example:

      once = Once()
      ...
      once.do(doSomething)
    """
    cdef Once once

    # FIXME cannot catch/pyreraise panic of .once ctor
    # https://github.com/cython/cython/issues/3165

    def do(PyOnce pyonce, object f):
        with nogil:
            _once_pydo(&pyonce.once, <PyObject *>f)

cdef void _once_pydo(Once *once, PyObject *f) nogil except *:
    __once_pydo(once, f)

cdef extern from * nogil:
    """
    static void __pyx_f_6golang_5_sync__pycall_fromnogil(PyObject *);
    static void __once_pydo(golang::sync::Once *once, PyObject *f) {
        once->do_([&]() {
            __pyx_f_6golang_5_sync__pycall_fromnogil(f);
        });
    }
    """
    void __once_pydo(Once *once, PyObject *f) except +topyexc

cdef void _pycall_fromnogil(PyObject *f) nogil except *:
    with gil:
        (<object>f)()


@final
cdef class PyWaitGroup:
    """WaitGroup allows to wait for collection of tasks to finish."""
    cdef WaitGroup wg

    # FIXME cannot catch/pyreraise panic of .wg ctor
    # https://github.com/cython/cython/issues/3165

    def done(PyWaitGroup pywg):
        with nogil:
            wg_done_pyexc(&pywg.wg)

    def add(PyWaitGroup pywg, int delta):
        with nogil:
            wg_add_pyexc(&pywg.wg, delta)

    def wait(PyWaitGroup pywg):
        with nogil:
            wg_wait_pyexc(&pywg.wg)


# ---- misc ----

cdef nogil:

    void semaacquire_pyexc(Sema *sema)      except +topyexc:
        sema.acquire()
    void semarelease_pyexc(Sema *sema)      except +topyexc:
        sema.release()

    void mutexlock_pyexc(Mutex *mu)         except +topyexc:
        mu.lock()
    void mutexunlock_pyexc(Mutex *mu)       except +topyexc:
        mu.unlock()

    void wg_done_pyexc(WaitGroup *wg)               except +topyexc:
        wg.done()
    void wg_add_pyexc(WaitGroup *wg, int delta)     except +topyexc:
        wg.add(delta)
    void wg_wait_pyexc(WaitGroup *wg)               except +topyexc:
        wg.wait()
