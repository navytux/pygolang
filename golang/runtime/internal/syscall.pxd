# cython: language_level=2
# Copyright (C) 2021-2022  Nexedi SA and Contributors.
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

from posix.fcntl cimport mode_t
from posix.stat cimport struct_stat

cdef extern from "golang/runtime/internal/syscall.h" namespace "golang::internal::syscall" nogil:
    int Close(int fd)
    int Fcntl(int fd, int cmd, int arg)
    int Fstat(int fd, struct_stat *out_st)
    int Open(const char *path, int flags, mode_t mode)
    int Read(int fd, void *buf, size_t count)
    int Write(int fd, const void *buf, size_t count)
