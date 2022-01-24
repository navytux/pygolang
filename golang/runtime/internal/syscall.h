#ifndef _NXD_LIBGOLANG_RUNTIME_INTERNAL_SYSCALL_H
#define _NXD_LIBGOLANG_RUNTIME_INTERNAL_SYSCALL_H

// Copyright (C) 2021-2022  Nexedi SA and Contributors.
//                          Kirill Smelkov <kirr@nexedi.com>
//
// This program is free software: you can Use, Study, Modify and Redistribute
// it under the terms of the GNU General Public License version 3, or (at your
// option) any later version, as published by the Free Software Foundation.
//
// You can also Link and Combine this program with other software covered by
// the terms of any of the Free Software licenses or any of the Open Source
// Initiative approved licenses and Convey the resulting work. Corresponding
// source of such a combination shall include the source code for all other
// software used.
//
// This program is distributed WITHOUT ANY WARRANTY; without even the implied
// warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
//
// See COPYING file for full licensing terms.
// See https://www.nexedi.com/licensing for rationale and options.

// Package syscall provides low-level interface to OS.

#include "golang/libgolang.h"

#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <signal.h>


// golang::internal::syscall::
namespace golang {
namespace internal {
namespace syscall {

// errors returned by system calls are represented as negative error codes, for example -ENOENT.
// Those error codes could be converted to error via NewErrno.
typedef int __Errno;
struct _Errno final : _error, object {
    __Errno syserr;

private:
    _Errno();
    ~_Errno();
    friend error NewErrno(__Errno syserr);
public:
    void incref();
    void decref();

public:
    // Error returns string corresponding to system error syserr.
    string Error();
};
typedef refptr<_Errno> Errno;

error NewErrno(__Errno syserr); // TODO better return Errno directly.

// system calls

int/*n|err*/ Read(int fd, void *buf, size_t count);
int/*n|err*/ Write(int fd, const void *buf, size_t count);

__Errno Close(int fd);
__Errno Fcntl(int fd, int cmd, int arg);
__Errno Fstat(int fd, struct ::stat *out_st);
int/*fd|err*/ Open(const char *path, int flags, mode_t mode);
__Errno Pipe(int vfd[2]);
__Errno Sigaction(int signo, const struct ::sigaction *act, struct ::sigaction *oldact);


}}} // golang::internal::syscall::

#endif  // _NXD_LIBGOLANG_RUNTIME_INTERNAL_SYSCALL_H
