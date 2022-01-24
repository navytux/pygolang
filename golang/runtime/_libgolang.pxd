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
"""pyx declarations for libgolang bits that are only interesting for runtimes."""

from libc.stdint cimport uint64_t
from posix.fcntl cimport mode_t
from posix.stat  cimport struct_stat

cdef extern from "golang/libgolang.h" namespace "golang" nogil:
    struct _libgolang_sema
    struct _libgolang_ioh
    enum _libgolang_runtime_flags:
        STACK_DEAD_WHILE_PARKED

    struct _libgolang_runtime_ops:
        _libgolang_runtime_flags  flags

        void    (*go)(void (*f)(void *) nogil, void *arg);

        _libgolang_sema* (*sema_alloc)  ()
        void             (*sema_free)   (_libgolang_sema*)
        void             (*sema_acquire)(_libgolang_sema*)
        void             (*sema_release)(_libgolang_sema*)

        void        (*nanosleep)(uint64_t)
        uint64_t    (*nanotime)()

        _libgolang_ioh* (*io_open)   (int* out_syserr, const char *path, int flags, mode_t mode)
        _libgolang_ioh* (*io_fdopen) (int* out_syserr, int sysfd)
        int             (*io_close)  (_libgolang_ioh* ioh)
        void            (*io_free)   (_libgolang_ioh* ioh)
        int             (*io_sysfd)  (_libgolang_ioh* ioh)
        int             (*io_read)   (_libgolang_ioh* ioh, void *buf, size_t count)
        int             (*io_write)  (_libgolang_ioh* ioh, const void *buf, size_t count)
        int             (*io_fstat)  (struct_stat* out_st, _libgolang_ioh* ioh)


    # XXX better take from golang.pxd, but there it is declared in `namespace
    # "golang"` which fails for C-mode compiles.
    void panic(const char *)
