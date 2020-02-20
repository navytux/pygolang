#ifndef _NXD_LIBGOLANG_SYNC_H
#define	_NXD_LIBGOLANG_SYNC_H

// Copyright (C) 2018-2020  Nexedi SA and Contributors.
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

// Package sync mirrors and amends Go package sync.
//
//  - `WorkGroup` allows to spawn group of goroutines working on a common task(*).
//  - `Once` allows to execute an action only once.
//  - `WaitGroup` allows to wait for a collection of tasks to finish.
//  - `Sema`(*), `Mutex` and `RWMutex` provide low-level synchronization.
//
// See also https://golang.org/pkg/sync for Go sync package documentation.
//
//
// C-level API
//
// Subset of sync package functionality is also provided via C-level API:
//
//  - `_makesema` and `_sema*` provide semaphore functionality(*).
//
// (*) not provided in Go standard library, but package
//     https://godoc.org/lab.nexedi.com/kirr/go123/xsync
//     provides corresponding Go equivalents.

#include <golang/libgolang.h>
#include <golang/context.h>

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

// RWMutex provides readers-writer mutex with preference for writers.
//
// https://en.wikipedia.org/wiki/Readers%E2%80%93writer_lock .
class RWMutex {
    Mutex           _g;
    chan<structZ>   _wakeupq; // closed & recreated every time to wakeup all waiters

    int  _nread_active;   // number of readers holding the lock
    int  _nwrite_waiting; // number of writers waiting for the lock
    bool _write_active;   // whether a writer is holding the lock

public:
    LIBGOLANG_API RWMutex();
    LIBGOLANG_API ~RWMutex();
    LIBGOLANG_API void Lock();
    LIBGOLANG_API void Unlock();
    LIBGOLANG_API void RLock();
    LIBGOLANG_API void RUnlock();

    // UnlockToRLock atomically downgrades write-locked RWMutex into read-locked.
    //
    // NOTE opposite operation - atomic upgrade from read-locked into
    // write-locked - is generally not possible due to deadlock if 2 threads
    // try to upgrade at the same time.
    LIBGOLANG_API void UnlockToRLock();

private:
    void _wakeup_all();

    RWMutex(const RWMutex&);    // don't copy
    RWMutex(RWMutex&&);         // don't move
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
    LIBGOLANG_API void do_(const func<void()> &f);

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

// WorkGroup is a group of goroutines working on a common task.
//
// Use .go() to spawn goroutines, and .wait() to wait for all of them to
// complete, for example:
//
//   sync::WorkGroup wg = sync::NewWorkGroup(ctx);
//   wg->go(f1);
//   wg->go(f2);
//   error err = wg->wait();
//
// Every spawned function accepts context related to the whole work and derived
// from ctx used to initialize WorkGroup, for example:
//
//   error f1(context::Context ctx) {
//       ...
//   }
//
// Whenever a function returns error, the work context is canceled indicating
// to other spawned goroutines that they have to cancel their work. .wait()
// waits for all spawned goroutines to complete and returns error, if any, from
// the first failed subtask.
//
// NOTE if spawned function panics, the panic is currently _not_ propagated to .wait().
//
// WorkGroup is modelled after https://godoc.org/golang.org/x/sync/errgroup but
// is not equal to it.
typedef refptr<class _WorkGroup> WorkGroup;
class _WorkGroup : public object {
    context::Context    _ctx;
    func<void()>        _cancel;
    WaitGroup           _wg;
    Mutex               _mu;
    error               _err;

    // don't new - create only via NewWorkGroup()
private:
    _WorkGroup();
    ~_WorkGroup();
    friend WorkGroup NewWorkGroup(context::Context ctx);
public:
    LIBGOLANG_API void decref();

public:
    LIBGOLANG_API void go(func<error(context::Context)> f);
    LIBGOLANG_API error wait();

private:
    _WorkGroup(const _WorkGroup&);  // don't copy
    _WorkGroup(_WorkGroup&&);       // don't move

    // internal API used by sync.pyx
    friend inline context::Context _WorkGroup_ctx(_WorkGroup *_wg);
};

// NewWorkGroup creates new WorkGroup working under ctx.
//
// See WorkGroup documentation for details.
LIBGOLANG_API WorkGroup NewWorkGroup(context::Context ctx);

// sync.pyx uses WorkGroup._ctx directly for efficiency.
#ifdef _LIBGOLANG_SYNC_INTERNAL_API
inline context::Context _WorkGroup_ctx(_WorkGroup *_wg) {
    return _wg->_ctx;
}
#endif

}}   // golang::sync::
#endif  // __cplusplus

#endif	// _NXD_LIBGOLANG_SYNC_H
