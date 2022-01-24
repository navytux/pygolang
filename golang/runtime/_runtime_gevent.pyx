# cython: language_level=2
# Copyright (C) 2019-2022  Nexedi SA and Contributors.
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

# Gevent runtime uses gevent's greenlets, semaphores and file objects.
# When sema.acquire() or IO blocks, gevent switches us from current to another greenlet.

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

from libc.stdint cimport uint8_t, uint64_t
from cpython cimport PyObject, Py_INCREF, Py_DECREF
from cython cimport final

from golang.runtime._libgolang cimport _libgolang_runtime_ops, _libgolang_sema, \
        _libgolang_ioh, STACK_DEAD_WHILE_PARKED, panic
from golang.runtime.internal cimport syscall
from golang.runtime cimport _runtime_thread
from golang.runtime._runtime_pymisc cimport PyExc, pyexc_fetch, pyexc_restore
from golang cimport topyexc

from libc.stdlib cimport calloc, free
from libc.errno  cimport EBADF
from posix.fcntl cimport mode_t, F_GETFL, F_SETFL, O_NONBLOCK, O_ACCMODE, O_RDONLY, O_WRONLY, O_RDWR
from posix.stat cimport struct_stat, S_ISREG, S_ISDIR, S_ISBLK
from posix.strings cimport bzero

from gevent.fileobject import FileObjectThread, FileObjectPosix


# _goviapy & _togo serve go
def _goviapy(_togo _ not None):
    with nogil:
        # run _.f in try/catch to workaround https://github.com/python-greenlet/greenlet/pull/285
        __goviapy(_.f, _.arg)
cdef nogil:
    void __goviapy(void (*f)(void *) nogil, void *arg) except +topyexc:
        f(arg)

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

    # ---- semaphore ----

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

    # ---- time ----

    void nanosleep(uint64_t dt):
        cdef PyExc exc
        with gil:
            pyexc_fetch(&exc)
            ok = _nanosleep(dt)
            pyexc_restore(exc)
        if not ok:
            panic("pyxgo: gevent: sleep: failed")

    # ---- IO ----

    struct IOH:
        PyObject* pygfobj # FileObjectPosix | FileObjectThread
        int       sysfd   # for direct access == pygfobj.fileno()

    _libgolang_ioh* io_open(int *out_syserr, const char *path, int flags, mode_t mode):
        # open the file and see in io_fdopen whether we can make its IO to be cooperative
        # no need to open with O_NONBLOCK because it does not affect anything at open time
        sysfd = syscall.Open(path, flags, mode)
        if sysfd < 0:
            out_syserr[0] = sysfd
            return NULL
        return io_fdopen(out_syserr, sysfd)

    _libgolang_ioh* io_fdopen(int *out_syserr, int sysfd):
        # close sysfd on any error
        ioh = _io_fdopen(out_syserr, sysfd)
        if ioh == NULL:
            syscall.Close(sysfd) # ignore err
        return ioh

    _libgolang_ioh* _io_fdopen(int *out_syserr, int sysfd):
        # check if we should enable O_NONBLOCK on this file-descriptor
        # even though we could enable O_NONBLOCK for regular files, it does not
        # work as expected as most unix'es report regular files as always read
        # and write ready.
        cdef struct_stat st
        cdef int syserr = syscall.Fstat(sysfd, &st)
        if syserr < 0:
            out_syserr[0] = syserr
            return NULL
        m = st.st_mode
        blocking = (S_ISREG(m) or S_ISDIR(m) or S_ISBLK(m)) # fd cannot refer to symlink

        # retrieve current sysfd flags and access mode
        flags = syscall.Fcntl(sysfd, F_GETFL, 0)
        if flags < 0:
            out_syserr[0] = flags
            return NULL
        acc = (flags & O_ACCMODE)

        # enable O_NONBLOCK if needed
        if not blocking:
            syserr = syscall.Fcntl(sysfd, F_SETFL, flags | O_NONBLOCK)
            if syserr < 0:
                out_syserr[0] = syserr
                return NULL

        # create IOH backed by FileObjectThread or FileObjectPosix
        ioh = <IOH*>calloc(1, sizeof(IOH))
        if ioh == NULL:
            panic("out of memory")

        cdef PyObject* pygfobj = NULL
        cdef PyExc exc
        with gil:
            pyexc_fetch(&exc)
            ok = __io_fdopen(&pygfobj, out_syserr, sysfd, blocking, acc)
            pyexc_restore(exc)
        if not ok:
            panic("pyxgo: gevent: io: fdopen: failed")

        if pygfobj == NULL:
            return NULL

        ioh.pygfobj = pygfobj
        ioh.sysfd   = sysfd
        return <_libgolang_ioh*>ioh
cdef:
    bint __io_fdopen(PyObject** ppygfobj, int *out_syserr, int sysfd, bint blocking, int acc):
        mode = 'b'
        if acc == O_RDONLY:
            mode += 'r'
        elif acc == O_WRONLY:
            mode += 'w'
        elif acc == O_RDWR:
            mode += 'w+'

        pygfobj = None
        try:
            if blocking:
                pygfobj = FileObjectThread(sysfd, mode=mode, buffering=0)
            else:
                pygfobj = FileObjectPosix(sysfd, mode=mode, buffering=0)
        except OSError as e:
            out_syserr[0] = -e.errno
        else:
            Py_INCREF(pygfobj)
            ppygfobj[0] = <PyObject*>pygfobj
            out_syserr[0] = 0

        return True


cdef nogil:
    int io_close(_libgolang_ioh* _ioh):
        ioh = <IOH*>_ioh
        cdef int syserr
        cdef PyExc exc  # XXX also save/restore errno (+everywhere)
        with gil:
            pyexc_fetch(&exc)
            ok = _io_close(ioh, &syserr)
            pyexc_restore(exc)
        if not ok:
            panic("pyxgo: gevent: io: close: failed")
        return syserr
cdef:
    bint _io_close(IOH* ioh, int* out_syserr):
        pygfobj = <object>ioh.pygfobj
        try:
            if ioh.sysfd == -1:
                out_syserr[0] = -EBADF
            else:
                pygfobj.close()
                ioh.sysfd = -1
                out_syserr[0] = 0
        except OSError as e:
            out_syserr[0] = -e.errno
        return True


cdef nogil:
    void io_free(_libgolang_ioh* _ioh):
        ioh = <IOH*>_ioh
        cdef PyExc exc
        with gil:
            pyexc_fetch(&exc)
            ok = _io_free(ioh)
            pyexc_restore(exc)
        if not ok:
            panic("pyxgo: gevent: io: free: failed")

        bzero(ioh, sizeof(IOH))
        free(ioh)
cdef:
    bint _io_free(IOH* ioh):
        pygfobj = <object>ioh.pygfobj
        ioh.pygfobj = NULL
        Py_DECREF(pygfobj)
        return True


cdef nogil:
    int io_sysfd(_libgolang_ioh* _ioh):
        ioh = <IOH*>_ioh
        return ioh.sysfd


cdef nogil:
    int io_read(_libgolang_ioh* _ioh, void *buf, size_t count):
        ioh = <IOH*>_ioh
        cdef int n
        cdef PyExc exc
        with gil:
            pyexc_fetch(&exc)
            ok = _io_read(ioh, &n, buf, count)
            pyexc_restore(exc)
        if not ok:
            panic("pyxgo: gevent: io: read: failed")
        return n
cdef:
    bint _io_read(IOH* ioh, int* out_n, void *buf, size_t count):
        pygfobj = <object>ioh.pygfobj
        cdef uint8_t[::1] mem = <uint8_t[:count]>buf
        xmem = memoryview(mem) # to avoid https://github.com/cython/cython/issues/3900 on mem[:0]=b''
        try:
            n = pygfobj.readinto(xmem)
        except OSError as e:
            n = -e.errno
        out_n[0] = n
        return True


cdef nogil:
    int io_write(_libgolang_ioh* _ioh, const void *buf, size_t count):
        ioh = <IOH*>_ioh
        cdef int n
        cdef PyExc exc
        with gil:
            pyexc_fetch(&exc)
            ok = _io_write(ioh, &n, buf, count)
            pyexc_restore(exc)
        if not ok:
            panic("pyxgo: gevent: io: write: failed")
        return n
cdef:
    bint _io_write(IOH* ioh, int* out_n, const void *buf, size_t count):
        pygfobj = <object>ioh.pygfobj
        cdef const uint8_t[::1] mem = <const uint8_t[:count]>buf
        try:
            n = pygfobj.write(mem)
        except OSError as e:
            n = -e.errno
        out_n[0] = n
        return True


    int io_fstat(struct_stat* out_st, _libgolang_ioh* _ioh):
        ioh = <IOH*>_ioh
        return syscall.Fstat(ioh.sysfd, out_st)


cdef nogil:

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
            io_open         = io_open,
            io_fdopen       = io_fdopen,
            io_close        = io_close,
            io_free         = io_free,
            io_sysfd        = io_sysfd,
            io_read         = io_read,
            io_write        = io_write,
            io_fstat        = io_fstat,
    )

from cpython cimport PyCapsule_New
libgolang_runtime_ops = PyCapsule_New(&gevent_ops,
        "golang.runtime._runtime_gevent.libgolang_runtime_ops", NULL)
