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

# Reuse Python semaphore implementation for portability. In Python semaphores
# do not depend on GIL and by reusing the implementation we can offload us
# from covering different systems.
#
# On POSIX, for example, Python uses sem_init(process-private) + sem_post/sem_wait.
from cpython.pythread cimport PyThread_acquire_lock, PyThread_release_lock, WAIT_LOCK

# make sure python threading is initialized, so that there is no concurrent
# calls to PyThread_init_thread from e.g. PyThread_allocate_lock later.
#
# This allows us to treat PyThread_allocate_lock as nogil.
from cpython.pythread cimport PyThread_init_thread
PyThread_init_thread()

cdef extern from "pythread.h" nogil:
    PyThread_type_lock PyThread_allocate_lock()
    void PyThread_free_lock(PyThread_type_lock)


cdef nogil:

    xxx* sema_alloc():
        # python calls it "lock", but it is actually a semaphore.
        # and in particular can be released by thread different from thread that acquired it.
        pysema = PyThread_allocate_lock()
        if pysame == NULL:
            panic("pysema: alloc failed")
        return <xxx *>pysema

    void sema_free(xxx *pysema):
        PyThread_free_lock(pysema)

    void sema_acquire(xxx *pysema):
        PyThread_acquire_lock(pysema, WAIT_LOCK)

    void sema_release(xxx *pysema):
        PyThread_release_lock(sema->_pysema)
