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
"""_runtime_gevent.pyx provides libgolang runtime based on gevent greenlets"""

# XXX 2 words about what we do/use gevent semaphores

from gevent.__semaphore cimport Semaphore
from cpython cimport Py_INCREF, Py_DECREF

from golang.runtime._libgolang cimport _libgolang_runtime_ops, _libgolang_sema, \
        STACK_DEAD_WHILE_PARKED, panic

from libc.stdio cimport printf  # XXX temp
import traceback

cdef nogil:

    # XXX better panic with pyexc object and detect that at recover side

    _libgolang_sema* sema_alloc():
        with gil:
            pygsema = Semaphore()
            printf('pygsema %p: alloc\tcounter=%d\n', <void*>pygsema, pygsema.counter)
            Py_INCREF(pygsema)
            return <_libgolang_sema*>pygsema
        # libgolang checks for NULL return

    bint _sema_free(_libgolang_sema *gsema):
        with gil:
            pygsema = <Semaphore>gsema
            printf('pygsema %p: free\tcounter=%d\n', <void*>pygsema, pygsema.counter)
            Py_DECREF(pygsema)
            return True
    void sema_free(_libgolang_sema *gsema):
        ok = _sema_free(gsema)
        if not ok:
            panic("pygsema: free: failed")

    bint _sema_acquire(_libgolang_sema *gsema):
        with gil:
            pygsema = <Semaphore>gsema
            printf('pygsema %p: acquire\tcounter=%d\n', <void*>pygsema, pygsema.counter)
            try:
                pygsema.acquire()
            except:
                printf('\nFAILED  %p: acquire\n\n', <void*>pygsema)
                #traceback.print_exc()
                raise
            return True
    void sema_acquire(_libgolang_sema *gsema):
        ok = _sema_acquire(gsema)
        if not ok:
            panic("pygsema: acquire: failed")

    bint _sema_release(_libgolang_sema *gsema):
        with gil:
            pygsema = <Semaphore>gsema
            printf('pygsema %p: release\tcounter=%d\n', <void*>pygsema, pygsema.counter)
            pygsema.release()
            return True
    void sema_release(_libgolang_sema *gsema):
        ok = _sema_release(gsema)
        if not ok:
            panic("pygsema: release: failed")


    # XXX const
    _libgolang_runtime_ops gevent_ops = _libgolang_runtime_ops(
            # XXX doc why
            flags           = STACK_DEAD_WHILE_PARKED,

            sema_alloc      = sema_alloc,
            sema_free       = sema_free,
            sema_acquire    = sema_acquire,
            sema_release    = sema_release,
    )

from cpython cimport PyCapsule_New
libgolang_runtime_ops = PyCapsule_New(&gevent_ops,
        "golang.runtime._runtime_gevent.libgolang_runtime_ops", NULL)
