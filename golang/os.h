#ifndef _NXD_LIBGOLANG_OS_H
#define _NXD_LIBGOLANG_OS_H
//
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
//
//  - `File` represents an opened file.
//  - `Open` opens file @path.
//  - `Pipe` creates new pipe.
//  - `NewFile` wraps OS-level file-descriptor into File.
//  - `ReadFile` returns content of file @path.
//  - `Signal` represents OS-level signal.
//
// See also https://golang.org/pkg/os for Go os package documentation.

#include <golang/libgolang.h>
#include <golang/runtime/internal/atomic.h>

#include <fcntl.h>

#include <tuple>

// golang::os::
namespace golang {
namespace os {

// ErrClosed is returned as cause by operations on closed File.
extern LIBGOLANG_API global<error> ErrClosed;

// File mimics os.File from Go.
// its methods return error with path and operation in context.
typedef refptr<class _File> File;
class _File : public object {
    _libgolang_ioh*  _ioh;
    string           _path;

    internal::atomic::int32ForkReset  _inflight; // # of currently inflight IO operations
    std::atomic<bool>                 _closed;

    // don't new - create via Open, NewFile, Pipe, ...
private:
    _File();
    ~_File();
    friend File _newFile(_libgolang_ioh* ioh, const string& name);
public:
    void decref();

public:
    LIBGOLANG_API string  Name()  const;
    LIBGOLANG_API error   Close();

    // Read implements io.Reader from Go: it reads into buf up-to count bytes.
    // TODO buf,count -> slice<byte>
    LIBGOLANG_API std::tuple<int, error> Read(void *buf, size_t count);

    // Write implements io.Writer from Go: it writes all data from buf.
    //
    // NOTE write behaves like io.Writer in Go - it tries to write as much
    // bytes as requested, and if it could write only less - it returns an error.
    //
    // TODO buf,count -> slice<byte>
    LIBGOLANG_API std::tuple<int, error> Write(const void *buf, size_t count);

    // Stat returns information about the file.
    LIBGOLANG_API error Stat(struct stat *st);

public:
    // _sysfd returns underlying OS file handle for the file.
    //
    // This handle is valid to use only until the File is alive and not closed.
    LIBGOLANG_API int _sysfd();

private:
    error _err(const char *op, error err);
};


// Open opens file @path.
LIBGOLANG_API std::tuple<File, error> Open(const string &path, int flags = O_RDONLY,
        mode_t mode = S_IRUSR | S_IWUSR | S_IXUSR |
                      S_IRGRP | S_IWGRP | S_IXGRP |
                      S_IROTH | S_IWOTH | S_IXOTH);

// NewFile wraps OS-level file-descriptor into File.
// The ownership of sysfd is transferred to File.
LIBGOLANG_API std::tuple<File, error> NewFile(int sysfd, const string& name);

// Pipe creates connected pair of files.
LIBGOLANG_API std::tuple</*r*/File, /*w*/File, error> Pipe();

// ReadFile returns content of file @path.
LIBGOLANG_API std::tuple<string, error> ReadFile(const string& path);


// Signal represents an OS signal.
//
// NOTE in Go os.Signal is interface while in pygolang os::Signal is concrete structure.
struct Signal {
    int signo;

    // String returns human-readable signal text.
    LIBGOLANG_API string String() const;

    // Signal == Signal
    inline bool operator==(const Signal& sig2) const { return (signo == sig2.signo); }
    inline bool operator!=(const Signal& sig2) const { return (signo != sig2.signo); }
};

// _Signal_from_int creates Signal from integer, for example from SIGINT.
LIBGOLANG_API Signal _Signal_from_int(int signo);

}} // golang::os::


// std::
namespace std {

// std::hash<Signal>
template<> struct hash<golang::os::Signal> {
    std::size_t operator()(const golang::os::Signal& sig) const noexcept {
        return hash<int>()(sig.signo);
    }
};

}   // std::

#endif  // _NXD_LIBGOLANG_OS_H
