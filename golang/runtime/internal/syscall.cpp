// Copyright (C) 2021-2023  Nexedi SA and Contributors.
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

#include "golang/runtime/internal/syscall.h"

#include <sys/types.h>
#include <sys/stat.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <string.h>
#include <unistd.h>

#include <string>


// golang::internal::syscall::
namespace golang {
namespace internal {
namespace syscall {

// ---- Errno ----

_Errno::_Errno() {}
_Errno::~_Errno() {}
void _Errno::incref() {
    object::incref();
}
void _Errno::decref() {
    if (__decref())
        delete this;
}

error NewErrno(__Errno syserr) {
    _Errno* _e = new _Errno();
    _e->syserr = syserr;
    return adoptref(static_cast<_error*>(_e));
}

string _Errno::Error() {
    _Errno& e = *this;

    char ebuf[128];
    bool ok;
#ifdef LIBGOLANG_OS_darwin
    ok = (::strerror_r(-e.syserr, ebuf, sizeof(ebuf)) == 0);
#elif defined(LIBGOLANG_OS_windows)
    ok = (::strerror_s(ebuf, sizeof(ebuf), -e.syserr) == 0);
#else
    char *estr = ::strerror_r(-e.syserr, ebuf, sizeof(ebuf));
    return string(estr);
#endif
    if (ok)
        return string(ebuf);
    return "unknown error " + std::to_string(-e.syserr);
}


// ---- syscalls ----
// TODO better call syscalls directly, instead of calling libc wrappers and saving/restoring errno

int Read(int fd, void *buf, size_t count) {
    int save_errno = errno;
    int n = ::read(fd, buf, count);
    if (n < 0)
        n = -errno;
    errno = save_errno;
    return n;
}

int Write(int fd, const void *buf, size_t count) {
    int save_errno = errno;
    int n = ::write(fd, buf, count);
    if (n < 0)
        n = -errno;
    errno = save_errno;
    return n;
}

__Errno Close(int fd) {
    int save_errno = errno;
    int err = ::close(fd);
    if (err < 0)
        err = -errno;
    errno = save_errno;
    return err;
}

#ifndef LIBGOLANG_OS_windows
__Errno Fcntl(int fd, int cmd, int arg) {
    int save_errno = errno;
    int err = ::fcntl(fd, cmd, arg);
    if (err < 0)
        err = -errno;
    errno = save_errno;
    return err;
}
#endif

__Errno Fstat(int fd, struct ::stat *out_st) {
    int save_errno = errno;
    int err = ::fstat(fd, out_st);
    if (err < 0)
        err = -errno;
    errno = save_errno;
    return err;
}

int Open(const char *path, int flags, mode_t mode) {
    int save_errno = errno;
#ifdef LIBGOLANG_OS_windows  // default to open files in binary mode
    if ((flags & (_O_TEXT | _O_BINARY)) == 0)
        flags |= _O_BINARY;
#endif
    int fd = ::open(path, flags, mode);
    if (fd < 0)
        fd = -errno;
    errno = save_errno;
    return fd;
}

__Errno Pipe(int vfd[2], int flags) {
    // supported flags: O_CLOEXEC
    if (flags & ~(O_CLOEXEC))
        return -EINVAL;
    int save_errno = errno;
    int err;
#ifdef LIBGOLANG_OS_linux
    err = ::pipe2(vfd, flags);
#elif defined(LIBGOLANG_OS_windows)
    err = ::_pipe(vfd, 4096, flags | _O_BINARY);
#else
    err = ::pipe(vfd);
    if (err)
        goto out;
    if (flags & O_CLOEXEC) {
        for (int i=0; i<2; i++) {
            err = Fcntl(vfd[i], F_SETFD, FD_CLOEXEC);
            if (err) {
                Close(vfd[0]);
                Close(vfd[1]);
                goto out;
            }
        }
    }
out:
#endif
    if (err == -1)
        err = -errno;
    errno = save_errno;
    return err;
}

#ifndef LIBGOLANG_OS_windows
__Errno Sigaction(int signo, const struct ::sigaction *act, struct ::sigaction *oldact) {
    int save_errno = errno;
    int err = ::sigaction(signo, act, oldact);
    if (err < 0)
        err = -errno;
    errno = save_errno;
    return err;
}
#endif

sighandler_t Signal(int signo, sighandler_t handler, int *out_psyserr) {
    int save_errno = errno;
    sighandler_t oldh = ::signal(signo, handler);
    *out_psyserr = (oldh == SIG_ERR
        ? (errno ? -errno : -EINVAL) // windows returns SIG_ERR/errno=0 for invalid signo
        : 0);
    errno = save_errno;
    return oldh;
}


}}} // golang::internal::syscall::
