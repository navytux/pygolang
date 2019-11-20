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
// See sync.h for package overview.

#include "golang/sync.h"

// golang::sync:: (except Sema and Mutex)
namespace golang {
namespace sync {

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

    chan<structZ> done = NULL;
    wg._mu.lock();
    if (wg._count != 0)
        done = wg._done;
    wg._mu.unlock();

    if (done == NULL)   // wg._count was =0
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
        if (err == NULL)
            return;

        g->_mu.lock();
        defer([&]() {
            g->_mu.unlock();
        });

        if (g->_err == NULL) {
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
