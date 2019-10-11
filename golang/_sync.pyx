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

from cython cimport final

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


# ---- misc ----

from golang cimport topyexc

cdef nogil:

    void semaacquire_pyexc(Sema *sema)      except +topyexc:
        sema.acquire()
    void semarelease_pyexc(Sema *sema)      except +topyexc:
        sema.release()

    void mutexlock_pyexc(Mutex *mu)         except +topyexc:
        mu.lock()
    void mutexunlock_pyexc(Mutex *mu)       except +topyexc:
        mu.unlock()
