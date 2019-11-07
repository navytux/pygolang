#ifndef _NXD_LIBGOLANG_SYNC_H
#define	_NXD_LIBGOLANG_SYNC_H

// Copyright (C) 2018-2019  Nexedi SA and Contributors.
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

// Package sync mirrors Go package sync.
//
//  - `Once` allows to execute an action only once.
//  - `WaitGroup` allows to wait for a collection of tasks to finish.
//  - `Sema` and `Mutex` provide low-level synchronization.
//
// See also https://golang.org/pkg/sync for Go sync package documentation.
//
//
// C-level API
//
// Subset of sync package functionality is also provided via C-level API:
//
//  - `_makesema` and `_sema*` provide semaphore functionality.

#include <golang/libgolang.h>

// ---- C-level API ----

#ifdef __cplusplus
namespace golang {
namespace sync {
extern "C" {
#endif

// _sema corresponds to sync.Sema
// no C-level analog is provided for sync.Mutex
typedef struct _sema _sema;
LIBGOLANG_API _sema *_makesema(void);
LIBGOLANG_API void _semafree(_sema *sema);
LIBGOLANG_API void _semaacquire(_sema *sema);
LIBGOLANG_API void _semarelease(_sema *sema);

#ifdef __cplusplus
}}} // golang::sync:: "C"
#endif


// ---- C++ API ----

#ifdef __cplusplus

// golang::sync::
namespace golang {
namespace sync {

// Sema provides semaphore.
class Sema {
    _sema *_gsema;

public:
    LIBGOLANG_API Sema();
    LIBGOLANG_API ~Sema();
    LIBGOLANG_API void acquire();
    LIBGOLANG_API void release();

private:
    Sema(const Sema&);      // don't copy
    Sema(Sema&&);           // don't move
};

// Mutex provides mutex.
class Mutex {
    Sema _sema;

public:
    LIBGOLANG_API Mutex();
    LIBGOLANG_API ~Mutex();
    LIBGOLANG_API void lock();
    LIBGOLANG_API void unlock();

private:
    Mutex(const Mutex&);    // don't copy
    Mutex(Mutex&&);         // don't move
};

// Once allows to execute an action only once.
//
// For example:
//
//   sync::Once once;
//   ...
//   once.do_(doSomething);
class Once {
    Mutex _mu;
    bool  _done;

public:
    LIBGOLANG_API Once();
    LIBGOLANG_API ~Once();
    LIBGOLANG_API void do_(const std::function<void(void)> &f);

private:
    Once(const Once&);      // don't copy
    Once(Once&&);           // don't move
};

// WaitGroup allows to wait for collection of tasks to finish.
class WaitGroup {
    Mutex          _mu;
    int            _count;
    chan<structZ>  _done;   // closed & recreated every time ._count drops to 0

public:
    LIBGOLANG_API WaitGroup();
    LIBGOLANG_API ~WaitGroup();
    LIBGOLANG_API void done();
    LIBGOLANG_API void add(int delta);
    LIBGOLANG_API void wait();

private:
    WaitGroup(const WaitGroup&);    // don't copy
    WaitGroup(WaitGroup&&);         // don't move
};

}}   // golang::sync::
#endif  // __cplusplus

#endif	// _NXD_LIBGOLANG_SYNC_H
