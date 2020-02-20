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

// Package sync mirrors Go package sync.
// See sync.h for package overview.

#include "golang/sync.h"

// golang::sync:: (except Sema and Mutex)
namespace golang {
namespace sync {

// RWMutex
RWMutex::RWMutex() {
    RWMutex& mu = *this;

    mu._wakeupq = makechan<structZ>();
    mu._nread_active    = 0;
    mu._nwrite_waiting  = 0;
    mu._write_active    = false;
}

RWMutex::~RWMutex() {}

// RWMutex implementation is based on
// https://en.wikipedia.org/wiki/Readers%E2%80%93writer_lock#Using_a_condition_variable_and_a_mutex
// but a channel ._wakeupq is used instead of condition variable.

// _wakeup_all simulates broadcast cond notification by waking up all current
// waiters and reallocating ._wakeupq for next round of queued waiters and
// wakeup.
//
// Must be called under ._g locked.
void RWMutex::_wakeup_all() {
    RWMutex& mu = *this;

    mu._wakeupq.close();
    mu._wakeupq = makechan<structZ>();
}

void RWMutex::RLock() {
    RWMutex& mu = *this;

    mu._g.lock();
    while (mu._nwrite_waiting > 0 || mu._write_active) {
        chan<structZ> wakeupq = mu._wakeupq;
        mu._g.unlock();
        wakeupq.recv();
        mu._g.lock();
    }

    mu._nread_active++;
    mu._g.unlock();
}

void RWMutex::RUnlock() {
    RWMutex& mu = *this;

    mu._g.lock();
    if (mu._nread_active <= 0) {
        mu._g.unlock();
        panic("sync: RUnlock of unlocked RWMutex");
    }
    mu._nread_active--;
    if (mu._nread_active == 0)
        mu._wakeup_all();
    mu._g.unlock();
}

void RWMutex::Lock() {
    RWMutex& mu = *this;

    mu._g.lock();
    mu._nwrite_waiting++;
    while (mu._nread_active > 0 || mu._write_active) {
        chan<structZ> wakeupq = mu._wakeupq;
        mu._g.unlock();
        wakeupq.recv();
        mu._g.lock();
    }

    mu._nwrite_waiting--;
    mu._write_active = true;
    mu._g.unlock();
}

void RWMutex::Unlock() {
    RWMutex& mu = *this;

    mu._g.lock();
    if (!mu._write_active) {
        mu._g.unlock();
        panic("sync: Unlock of unlocked RWMutex");
    }
    mu._write_active = false;
    mu._wakeup_all();

    mu._g.unlock();
}

void RWMutex::UnlockToRLock() {
    RWMutex& mu = *this;

    mu._g.lock();
    if (!mu._write_active) {
        mu._g.unlock();
        panic("sync: UnlockToRLock of unlocked RWMutex");
    }
    mu._write_active = false;
    mu._nread_active++;
    mu._wakeup_all();
    mu._g.unlock();
}


// Once
Once::Once() {
    Once *once = this;
    once->_done = false;
}

Once::~Once() {}

void Once::do_(const func<void()> &f) {
    Once *once = this;
    once->_mu.lock();
    defer([&]() {
        once->_mu.unlock();
    });

    if (!once->_done) {
        once->_done = true;
        f();
    }
}

// WaitGroup
WaitGroup::WaitGroup() {
    WaitGroup& wg = *this;
    wg._count = 0;
    wg._done  = makechan<structZ>();
}

WaitGroup::~WaitGroup() {}

void WaitGroup::done() {
    WaitGroup& wg = *this;
    wg.add(-1);
}

void WaitGroup::add(int delta) {
    WaitGroup& wg = *this;

    if (delta == 0)
        return;

    wg._mu.lock();
    defer([&]() {
        wg._mu.unlock();
    });

    wg._count += delta;
    if (wg._count < 0)
        panic("sync: negative WaitGroup counter");
    if (wg._count == 0) {
        wg._done.close();
        wg._done = makechan<structZ>();
    }
}

void WaitGroup::wait() {
    WaitGroup& wg = *this;

    chan<structZ> done = nil;
    wg._mu.lock();
    if (wg._count != 0)
        done = wg._done;
    wg._mu.unlock();

    if (done == nil)    // wg._count was =0
        return;

    done.recv();
}

// WorkGroup
_WorkGroup::_WorkGroup()  {}
_WorkGroup::~_WorkGroup() {}
void _WorkGroup::decref() {
    if (__decref())
        delete this;
}

WorkGroup NewWorkGroup(context::Context ctx) {
    WorkGroup g = adoptref(new _WorkGroup());

    tie(g->_ctx, g->_cancel) = context::with_cancel(ctx);
    return g;
}

void _WorkGroup::go(func<error(context::Context)> f) {
    // NOTE = refptr<_WorkGroup> because we pass ref to g to spawned worker.
    WorkGroup g = newref(this);

    g->_wg.add(1);

    golang::go([g, f]() {       // NOTE g ref passed to spawned worker
        defer([&]() {
            g->_wg.done();
        });

        error err = f(g->_ctx); // TODO consider also propagating panic
        if (err == nil)
            return;

        g->_mu.lock();
        defer([&]() {
            g->_mu.unlock();
        });

        if (g->_err == nil) {
            // this goroutine is the first failed task
            g->_err = err;
            g->_cancel();
        }
    });
}

error _WorkGroup::wait() {
    _WorkGroup& g = *this;

    g._wg.wait();
    g._cancel();
    return g._err;
}

}}  // golang::sync::
