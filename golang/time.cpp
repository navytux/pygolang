// Copyright (C) 2019  Nexedi SA and Contributors.
//                     Kirill Smelkov <kirr@nexedi.com>
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

// Package time mirrors Go package time.
// See time.h for package overview.

#include "golang/time.h"

#include <math.h>

using std::function;


// golang::time:: (except sleep and now)
namespace golang {
namespace time {

// ---- timers ----
// FIXME timers are implemented very inefficiently - each timer currently consumes a goroutine.

refptr<Ticker> new_ticker(double dt);
refptr<Timer>  new_timer (double dt);
refptr<Timer>  _new_timer(double dt, function<void()>);


chan<double> tick(double dt) {
    if (dt <= 0)
        return NULL;
    return new_ticker(dt)->c;
}

chan<double> after(double dt) {
    return new_timer(dt)->c;
}

refptr<Timer> after_func(double dt, function<void()> f) {
    return _new_timer(dt, f);
}

// Ticker
Ticker::Ticker()  {}
Ticker::~Ticker() {}
void Ticker::decref() {
    if (__decref())
        delete this;
}

refptr<Ticker> new_ticker(double dt) {
    if (dt <= 0)
        panic("ticker: dt <= 0");

    refptr<Ticker> tx = adoptref(new Ticker());
    tx->c     = makechan<double>(1); // 1-buffer -- same as in Go
    tx->_dt   = dt;
    tx->_stop = false;
    go([tx]() {
        tx->_tick();
    });
    return tx;
}

void Ticker::stop() {
    Ticker &tx = *this;

    tx._mu.lock();
    tx._stop = true;

    // drain what _tick could have been queued already
    while (tx.c.len() > 0)
        tx.c.recv();
    tx._mu.unlock();
}

void Ticker::_tick() {
    Ticker &tx = *this;

    while (1) {
        // XXX adjust for accumulated error δ?
        sleep(tx._dt);

        tx._mu.lock();
        if (tx._stop) {
            tx._mu.unlock();
            return;
        }

        // send from under ._mu so that .stop can be sure there is no
        // ongoing send while it drains the channel.
        double t = now();
        select({
            _default,
            tx.c.sends(&t),
        });
        tx._mu.unlock();
    }
}


// Timer
Timer::Timer()  {}
Timer::~Timer() {}
void Timer::decref() {
    if (__decref())
        delete this;
}

refptr<Timer> _new_timer(double dt, function<void()> f) {
    refptr<Timer> t = adoptref(new Timer());
    t->c    = (f == NULL ? makechan<double>(1) : NULL);
    t->_f   = f;
    t->_dt  = INFINITY;
    t->_ver = 0;
    t->reset(dt);
    return t;
}

refptr<Timer> new_timer(double dt) {
    return _new_timer(dt, NULL);
}

bool Timer::stop() {
    Timer &t = *this;
    bool canceled;

    t._mu.lock();

    if (t._dt == INFINITY) {
        canceled = false;
    }
    else {
        t._dt  = INFINITY;
        t._ver += 1;
        canceled = true;
    }

    // drain what _fire could have been queued already
    while (t.c.len() > 0)
        t.c.recv();

    t._mu.unlock();
    return canceled;
}

void Timer::reset(double dt) {
    Timer &t = *this;

    t._mu.lock();
    if (t._dt != INFINITY) {
        t._mu.unlock();
        panic("Timer.reset: the timer is armed; must be stopped or expired");
    }
    t._dt  = dt;
    t._ver += 1;
    // TODO rework timers so that new timer does not spawn new goroutine.
    refptr<Timer> tref = newref(&t); // pass t reference to spawned goroutine
    go([tref, dt](int ver) {
        tref->_fire(dt, ver);
    }, t._ver);
    t._mu.unlock();
}

void Timer::_fire(double dt, int ver) {
    Timer &t = *this;

    sleep(dt);
    t._mu.lock();
    if (t._ver != ver) {
        t._mu.unlock();
        return; // the timer was stopped/resetted - don't fire it
    }
    t._dt = INFINITY;

    // send under ._mu so that .stop can be sure that if it sees
    // ._dt = INFINITY, there is no ongoing .c send.
    if (t._f == NULL) {
        t.c.send(now());
        t._mu.unlock();
        return;
    }
    t._mu.unlock();

    // call ._f not from under ._mu not to deadlock e.g. if ._f wants to reset the timer.
    t._f();
}

}}  // golang::time::
