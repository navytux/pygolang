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
"""_runtime_gevent.pyx provides libgolang runtime based on gevent greenlets."""

from __future__ import print_function, absolute_import

# Gevent runtime uses gevent's greenlets.

IF not PYPY:
    from gevent._greenlet cimport Greenlet
ELSE:
    # on pypy gevent does not compile greenlet.py citing that
    # "there is no greenlet.h on pypy"
    from gevent.greenlet import Greenlet

from gevent import sleep as pygsleep

from libc.stdint cimport uint64_t
from cpython cimport Py_INCREF, Py_DECREF
from cython cimport final

from golang.runtime._libgolang cimport _libgolang_runtime_ops, panic
from golang.runtime cimport _runtime_thread


# _goviapy & _togo serve go
def _goviapy(_togo _ not None):
    with nogil:
        _.f(_.arg)

@final
cdef class _togo:
    cdef void (*f)(void *) nogil
    cdef void *arg


cdef nogil:

    # XXX better panic with pyexc object and detect that at recover side?

    bint _go(void (*f)(void *), void *arg):
        with gil:
            _ = _togo(); _.f = f; _.arg = arg
            g = Greenlet(_goviapy, _)
            g.start()
            return True

    void go(void (*f)(void *), void *arg):
        ok = _go(f, arg)
        if not ok:
            panic("pyxgo: gevent: go: failed")


    bint _nanosleep(uint64_t dt):
        cdef double dt_s = dt * 1E-9
        with gil:
            pygsleep(dt_s)
            return True
    void nanosleep(uint64_t dt):
        ok = _nanosleep(dt)
        if not ok:
            panic("pyxgo: gevent: sleep: failed")


    # XXX const
    _libgolang_runtime_ops gevent_ops = _libgolang_runtime_ops(
            go              = go,
            nanosleep       = nanosleep,
            nanotime        = _runtime_thread.nanotime, # reuse from _runtime_thread
    )

from cpython cimport PyCapsule_New
libgolang_runtime_ops = PyCapsule_New(&gevent_ops,
        "golang.runtime._runtime_gevent.libgolang_runtime_ops", NULL)
