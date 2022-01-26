// Copyright (C) 2019-2022  Nexedi SA and Contributors.
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

// Package os mirrors Go package os.
// See os.h for package overview.

#include "golang/errors.h"
#include "golang/fmt.h"
#include "golang/io.h"
#include "golang/os.h"
#include "golang/time.h"

#include "golang/runtime/internal.h"
#include "golang/runtime/internal/syscall.h"

#include <unistd.h>
#include <string.h>
#include <signal.h>

// GLIBC >= 2.32 provides sigdescr_np but not sys_siglist in its headers
// GLIBC <  2.32 provides sys_siglist but not sigdescr_np in its headers
// cut this short
// (on darwing sys_siglist declaration is normally provided)
#ifndef __APPLE__
extern "C" {
    extern const char * const sys_siglist[];
}
#endif

using golang::internal::_runtime;
namespace sys = golang::internal::syscall;

using std::tuple;
using std::make_tuple;
using std::tie;
using std::vector;

// golang::os::
namespace golang {
namespace os {

global<error> ErrClosed = errors::New("file already closed");

// TODO -> os.PathError
static error _pathError(const char *op, const string &path, error err);

// File
string _File::Name() const { return _path; }

_File::_File() {}
_File::~_File() {}
void _File::decref() {
    if (__decref()) {
        _File& f = *this;
        f.Close(); // ignore error
        _runtime->io_free(f._ioh);
        f._ioh = nil;
        delete this;
    }
}

File _newFile(_libgolang_ioh* ioh, const string& name) {
    File f = adoptref(new _File);
    f->_path = name;
    f->_ioh  = ioh;
    f->_inflight.store(0);
    f->_closed.store(false);
    return f;
}

tuple<File, error> Open(const string &path, int flags, mode_t mode) {
    int syserr;
    _libgolang_ioh* ioh = _runtime->io_open(&syserr,
                                            path.c_str(), flags, mode);
    if (syserr != 0)
        return make_tuple(nil, _pathError("open", path, sys::NewErrno(syserr)));

    return make_tuple(_newFile(ioh, path), nil);
}

tuple<File, error> NewFile(int sysfd, const string& name) {
    int syserr;
    _libgolang_ioh* ioh = _runtime->io_fdopen(&syserr, sysfd);
    if (syserr != 0)
        return make_tuple(nil, _pathError("fdopen", name, sys::NewErrno(syserr)));

    return make_tuple(_newFile(ioh, name), nil);
}

error _File::Close() {
    _File& f = *this;

    bool x = false;
    if (!f._closed.compare_exchange_strong(x, true))
        return f._err("close", ErrClosed);

    // wait till all currently-inprogress IO is complete
    //
    // TODO try to interrupt those inprogress IO calls.
    // It is not so easy however - for example on Linux sys_read from pipe is
    // not interrupted by sys_close of that pipe. sys_read/sys_write on regular
    // files are also not interrupted by sys_close. For sockets we could use
    // sys_shutdown, but shutdown does not work for anything else but sockets.
    //
    // NOTE1 with io_uring any inflight operation can be cancelled.
    // NOTE2 under gevent io_close does interrupt outstanding IO, at least for
    // pollable file descriptors, with `cancel_wait_ex: [Errno 9] File
    // descriptor was closed in another greenlet` exception.
    //
    // For now we use simplest-possible way to wait until all IO is complete.
    while (1) {
        if (f._inflight.load() == 0)
            break;
        time::sleep(1*time::microsecond);
    }

    int syserr = _runtime->io_close(f._ioh);
    if (syserr != 0)
        return f._err("close", sys::NewErrno(syserr));

    return nil;
}

int _File::_sysfd() {
    _File& f = *this;

    f._inflight.fetch_add(+1);
    defer([&]() {
        f._inflight.fetch_add(-1);
    });
    if (f._closed.load())
        return -1; // bad file descriptor

    return _runtime->io_sysfd(f._ioh);
}

tuple<int, error> _File::Read(void *buf, size_t count) {
    _File& f = *this;
    int n;

    f._inflight.fetch_add(+1);
    defer([&]() {
        f._inflight.fetch_add(-1);
    });
    if (f._closed.load())
        return make_tuple(0, f._err("read", ErrClosed));

    n = _runtime->io_read(f._ioh, buf, count);
    if (n == 0)
        return make_tuple(n, io::EOF_);
    if (n < 0)
        return make_tuple(0, f._err("read", sys::NewErrno(n)));

    return make_tuple(n, nil);
}

tuple<int, error> _File::Write(const void *buf, size_t count) {
    _File& f = *this;
    int n, wrote=0;

    f._inflight.fetch_add(+1);
    defer([&]() {
        f._inflight.fetch_add(-1);
    });
    if (f._closed.load())
        return make_tuple(0, f._err("write", ErrClosed));

    // NOTE contrary to write(2) we have to write all data as io.Writer requires.
    while (count != 0) {
        n = _runtime->io_write(f._ioh, buf, count);
        if (n < 0)
            return make_tuple(wrote, f._err("write", sys::NewErrno(n)));

        wrote += n;
        buf    = ((const char *)buf) + n;
        count -= n;
    }

    return make_tuple(wrote, nil);
}

error _File::Stat(struct stat *st) {
    _File& f = *this;

    f._inflight.fetch_add(+1);
    defer([&]() {
        f._inflight.fetch_add(-1);
    });
    if (f._closed.load())
        return f._err("stat", ErrClosed);

    int syserr = _runtime->io_fstat(st, f._ioh);
    if (syserr != 0)
        return f._err("stat", sys::NewErrno(syserr));
    return nil;
}


tuple<string, error> ReadFile(const string& path) {
    // errctx is ok as returned by all calls.
    File  f;
    error err;

    tie(f, err) = Open(path);
    if (err != nil)
        return make_tuple("", err);

    string data;
    vector<char> buf(4096);

    while (1) {
        int n;
        tie(n, err) = f->Read(&buf[0], buf.size());
        data.append(&buf[0], n);
        if (err != nil) {
            if (err == io::EOF_)
                err = nil;
            break;
        }
    }

    error err2 = f->Close();
    if (err == nil)
        err = err2;
    if (err != nil)
        data = "";
    return make_tuple(data, err);
}


// pipe

tuple<File, File, error> Pipe() {
    int vfd[2], syserr;
    syserr = sys::Pipe(vfd);
    if (syserr != 0)
        return make_tuple(nil, nil, fmt::errorf("pipe: %w", sys::NewErrno(syserr)));

    File r, w;
    error err;
    tie(r, err) = NewFile(vfd[0], "|0");
    if (err != nil) {
        return make_tuple(nil, nil, fmt::errorf("pipe: |0: %w", err));
    }
    tie(w, err) = NewFile(vfd[1], "|1");
    if (err != nil) {
        r->Close(); // ignore err
        return make_tuple(nil, nil, fmt::errorf("pipe: |1: %w", err));
    }

    return make_tuple(r, w, nil);
}


// _err returns error corresponding to op(file) and underlying error err.
error _File::_err(const char *op, error err) {
    _File& f = *this;
    return _pathError(op, f._path, err);
}

// _pathError returns os.PathError-like for op/path and underlying error err.
static error _pathError(const char *op, const string &path, error err) {
    // TODO use fmt::v and once it lands in
//  return fmt::errorf("%s %s: %s", op, v(path), err));
    return fmt::errorf("%s %s: %w", op, path.c_str(), err);
}


string Signal::String() const {
    const Signal& sig = *this;
    const char *sigstr = nil;

    if (0 <= sig.signo && sig.signo < NSIG)
        sigstr = ::sys_siglist[sig.signo]; // might be nil as well

    if (sigstr != nil)
        return string(sigstr);

    return fmt::sprintf("signal%d", sig.signo);
}

Signal _Signal_from_int(int signo) {
    Signal sig;
    sig.signo = signo;
    return sig;
}

}}  // golang::os::
