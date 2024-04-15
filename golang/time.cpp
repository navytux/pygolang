// Copyright (C) 2019-2024  Nexedi SA and Contributors.
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

// Package time mirrors Go package time.
// See time.h for package overview.

#include "golang/time.h"
#include "timer-wheel.h"


#define DEBUG 0
#if DEBUG
#  define debugf(format, ...) fprintf(stderr, format, ##__VA_ARGS__)
#else
#  define debugf(format, ...) do {} while (0)
#endif


// golang::sync:: (private imports)
namespace golang {
namespace sync {

bool _semaacquire_timed(_sema *sema, uint64_t timeout_ns);

}}  // golang::sync::


// golang::time:: (except sleep and now)
namespace golang {
namespace time {

// ---- timers ----

Ticker new_ticker(double dt);
Timer  new_timer (double dt);
Timer  _new_timer(double dt, func<void()>);


chan<double> tick(double dt) {
    if (dt <= 0)
        return nil;
    return new_ticker(dt)->c;
}

chan<double> after(double dt) {
    return new_timer(dt)->c;
}

Timer after_func(double dt, func<void()> f) {
    return _new_timer(dt, f);
}

Timer new_timer(double dt) {
    return _new_timer(dt, nil);
}


// Ticker (small wrapper around Timer)
_Ticker::_Ticker()  {}
_Ticker::~_Ticker() {}
void _Ticker::decref() {
    if (__decref())
        delete this;
}

Ticker new_ticker(double dt) {
    if (dt <= 0)
        panic("ticker: dt <= 0");

    Ticker tx = adoptref(new _Ticker());
    tx->c     = makechan<double>(1); // 1-buffer -- same as in Go
    tx->_dt   = dt;
    tx->_stop = false;
    tx->_timer = after_func(dt, [tx]() { tx ->_tick(); });
    return tx;
}

void _Ticker::stop() {
    _Ticker &tx = *this;

    tx._mu.lock();
    tx._stop = true;
    if (tx._timer != nil) {
        tx._timer->stop();
        tx._timer = nil;  // break Ticker -> Timer -> _tick -> Ticker cycle
    }

    // drain what _tick could have been queued already
    while (tx.c.len() > 0)
        tx.c.recv();
    tx._mu.unlock();
}

void _Ticker::_tick() {
    _Ticker &tx = *this;

    tx._mu.lock();
    if (tx._stop) {
        tx._mu.unlock();
        return;
    }

    // XXX adjust for accumulated error δ?
    tx._timer->reset(tx._dt);

    // send from under ._mu so that .stop can be sure there is no
    // ongoing send while it drains the channel.
    double t = now();
    select({
        _default,
        tx.c.sends(&t),
    });
    tx._mu.unlock();
}


// Timers
//
// Timers are implemented via Timer Wheel.
// For this time arrow is divided into equal periods named ticks, and Ratas
// library[1] is used to manage timers with granularity of ticks. We employ
// ticks to avoid unnecessary overhead of managing timeout-style timers with
// nanosecond precision.
//
// Let g denote tick granularity.
//
// The timers are provided with guaranty that their expiration happens after
// requested expiration time. In other words the following invariant is always true:
//
//      t(exp) ≤ t(fire)
//
// we also want that firing _ideally_ happens not much far away from requested
// expiration time, meaning that the following property is aimed for, but not guaranteed:
//
//               t(fire) < t(exp) + g
//
// a tick Ti is associated with [i-1,i)·g time range. It is said that tick Ti
// "happens" at i·g point in time. Firing of timers associated with tick Ti is
// done when Ti happens - ideally at i·g time or strictly speaking ≥ that point.
//
// When timers are armed their expiration tick is set as Texp = ⌊t(exp)/g+1⌋ to
// be in time range that tick Texp covers.
//
//
// A special goroutine, _timer_loop, is dedicated to advance time of the
// timer-wheel as ticks happen, and to run expired timers. When there is
// nothing to do that goroutine pauses itself and goes to sleep until either
// next expiration moment, or until new timer with earlier expiration time is
// armed. To be able to simultaneously select on those two condition a
// semaphore with acquisition timeout is employed. Please see _tSema for
// details.
//
//
// [1] Ratas - A hierarchical timer wheel.
//     https://www.snellman.net/blog/archive/2016-07-27-ratas-hierarchical-timer-wheel,
//     https://github.com/jsnell/ratas

// Tns indicates time measured in nanoseconds.
// It is used for documentation purposes mainly to distinguish from the time measured in ticks.
typedef uint64_t Tns;

// _tick_g is ticks granularity in nanoseconds.
static const Tns _tick_g = 1024;   // 1 tick is ~ 1 μs


// timer-wheel holds registry of all timers and manages them.
static sync::Mutex* _tWheelMu;  // lock for timer wheel + sleep/wakeup channel (see _tSema & co below)
static TimerWheel*  _tWheel;    // for each timer the wheel holds 1 reference to _TimerImpl object

// _TimerImpl amends _Timer with timer-wheel entry and implementation-specific state.
enum _TimerState {
    _TimerDisarmed, // timer is not registered to timer wheel and is not firing
    _TimerArmed,    // timer is     registered to timer wheel and is not firing
    _TimerFiring    // timer is currently firing  (and not on the timer wheel)
};
struct _TimerImpl : _Timer {
    void _fire();
    void _queue_fire();
    MemberTimerEvent<_TimerImpl, &_TimerImpl::_queue_fire>  _tWheelEntry;

    func<void()> _f;

    sync::Mutex _mu;
    _TimerState _state;

    // entry on "firing" list; see _tFiring for details
    _TimerImpl* _tFiringNext;   // TODO could reuse _tWheelEntry.{next_,prev_} for "firing" list

    _TimerImpl();
    ~_TimerImpl();
};

_TimerImpl::_TimerImpl() : _tWheelEntry(this) {}
_TimerImpl::~_TimerImpl() {}

_Timer::_Timer()  {}
_Timer::~_Timer() {}
void _Timer::decref() {
    if (__decref())
        delete static_cast<_TimerImpl*>(this);
}


// _tSema and _tSleeping + _tWaking organize sleep/wakeup channel.
//
// Timer loop uses wakeup sema to both:
//   * sleep until next timer expires, and
//   * become woken up earlier if new timer with earlier expiration time is armed
//
// _tSleeping + _tWaking are used by the timer loop and clients to coordinate
// _tSema operations, so that the value of sema is always 0 or 1, and that
// every new loop cycle starts with sema=0, meaning that sema.Acquire will block.
//
// Besides same.Acquire, all operations on the sleep/wakeup channel are done under _tWheelMu.
static sync::_sema* _tSema;
static bool         _tSleeping; // 1 iff timer loop:
                                //   \/ decided to go to sleep on wakeup sema
                                //   \/ sleeps on wakeup sema via Acquire
                                //   \/ woken up after Acquire before setting _tSleeping=0 back
static bool         _tWaking;   // 1 iff client timer arm:
                                //   /\ saw _tSleeping=1 && _tWaking=0 and decided to do wakeup
                                //   /\ (did Release \/ will do Release)
                                //   /\ until timer loop set back _tWaking=0
static Tns          _tSleeping_until; // until when timer loop is sleeping if _tSleeping=1


// _timer_loop implements timer loop: it runs in dedicated goroutine ticking the
// timer-wheel and sleeping in between ticks.
static void _timer_loop();
static void _timer_loop_fire_queued();
void _init() {
    _tWheelMu  = new sync::Mutex();
    _tWheel    = new TimerWheel(_nanotime() / _tick_g);
    _tSema     = sync::_makesema();  sync::_semaacquire(_tSema); // 1 -> 0
    _tSleeping = false;
    _tWaking   = false;
    _tSleeping_until = 0;
    go(_timer_loop);
}

static void _timer_loop() {
    while (1) {
        // tick the wheel. This puts expired timers on firing list but delays
        // really firing them until we release _tWheelMu.
        _tWheelMu->lock();
        Tick now_t  = _nanotime() / _tick_g;
        Tick wnow_t = _tWheel->now();
        Tick wdt_t  = now_t - wnow_t;
        debugf("LOOP: now_t: %lu  wnow_t: %lu  δ_t %lu ...\n", now_t, wnow_t, wdt_t);
        if (now_t > wnow_t)          // advance(0) panics. Avoid that if we wake up earlier
            _tWheel->advance(wdt_t); // inside the same tick, e.g. due to signal.
        _tWheelMu->unlock();

        // fire the timers queued on the firing list
        _timer_loop_fire_queued();


        // go to sleep until next timer expires or wakeup comes from new arming.
        //
        // limit max sleeping time because contrary to other wheel operations -
        // - e.g. insert and delete which are O(1), the complexity of
        // ticks_to_next_event is O(time till next expiry).
        Tns tsleep_max = 1*1E9; // 1s
        bool sleeping = false;

        _tWheelMu->lock();
        Tick wsleep_t = _tWheel->ticks_to_next_event(tsleep_max / _tick_g);
        Tick wnext_t  = _tWheel->now() + wsleep_t;

        Tns tnext = wnext_t * _tick_g;
        Tns tnow  = _nanotime();

        if (tnext > tnow) {
            _tSleeping = sleeping = true;
            _tSleeping_until = tnext;
        }
        _tWheelMu->unlock();

        if (!sleeping)
            continue;

        Tns tsleep = tnext - tnow;
        debugf("LOOP: sleeping %.3f μs ...\n", tsleep / 1e3);

        bool acq = sync::_semaacquire_timed(_tSema, tsleep);

        // bring sleep/wakeup channel back into reset state with S=0
        _tWheelMu->lock();
        //  acq ^  waking   Release was done while Acquire was blocked                       S=0
        //  acq ^ !waking   impossible
        // !acq ^  waking   Acquire finished due to timeout;    Release was done after that  S=1
        // !acq ^ !waking   Acquire finished due to timeout; no Release was done at all      S=0

        debugf("LOOP: woken up  acq=%d  waking=%d\n", acq, _tWaking);

        if ( acq && !_tWaking) {
            _tWheelMu->unlock();
            panic("BUG: timer loop: woken up with acq ^ !waking");
        }
        if (!acq &&  _tWaking) {
            acq = sync::_semaacquire_timed(_tSema, 0); // S=1 -> acquire should be immediate
            if (!acq) {
                _tWheelMu->unlock();
                panic("BUG: timer loop: reacquire after acq ^ waking failed");
            }
        }

        _tSleeping = false;
        _tWaking   = false;
        _tSleeping_until = 0;
        _tWheelMu->unlock();
    }
}

Timer _new_timer(double dt, func<void()> f) {
    _TimerImpl* _t = new _TimerImpl();

    _t->c    = (f == nil ? makechan<double>(1) : nil);
    _t->_f   = f;
    _t->_state = _TimerDisarmed;
    _t->_tFiringNext = nil;

    Timer t = adoptref(static_cast<_Timer*>(_t));
    t->reset(dt);
    return t;
}

void _Timer::reset(double dt) {
    _TimerImpl& t = *static_cast<_TimerImpl*>(this);

    if (dt <= 0)
        dt = 0;

    Tns  when   = _nanotime() + Tns(dt*1e9);
    Tick when_t = when / _tick_g + 1;  // Ti covers [i-1,i)·g

    _tWheelMu->lock();
    t._mu.lock();
    if (t._state != _TimerDisarmed) {
        t._mu.unlock();
        _tWheelMu->unlock();
        panic("Timer.reset: the timer is armed; must be stopped or expired");
    }
    t._state = _TimerArmed;

    Tick wnow_t = _tWheel->now();
    Tick wdt_t;
    if (when_t > wnow_t)
        wdt_t = when_t - wnow_t;
    else
        wdt_t = 1; // schedule(0) panics

    // the wheel will keep a reference to the timer
    t.incref();

    _tWheel->schedule(&t._tWheelEntry, wdt_t);
    t._mu.unlock();

    // wakeup timer loop if it is sleeping until later than new timer expiry
    if (_tSleeping) {
        if ((when < _tSleeping_until) && !_tWaking) {
            debugf("USER: waking up loop\n");
            _tWaking = true;
            sync::_semarelease(_tSema);
        }
    }

    _tWheelMu->unlock();
}

bool _Timer::stop() {
    _TimerImpl& t = *static_cast<_TimerImpl*>(this);
    bool canceled;

    _tWheelMu->lock();
    t._mu.lock();

    switch (t._state) {
    case _TimerDisarmed:
        canceled = false;
        break;

    case _TimerArmed:
        // timer wheel is holding this timer entry. Remove it from there.
        t._tWheelEntry.cancel();
        t.decref();
        canceled = true;
        break;

    case _TimerFiring:
        // the timer is on "firing" list. Timer loop will process it and skip
        // upon seeing ._state = _TimerDisarmed. It will also be the timer loop
        // to drop the reference to the timer that timer-wheel was holding.
        canceled = true;
        break;

    default:
        panic("invalid timer state");

    }

    if (canceled)
        t._state = _TimerDisarmed;

    // drain what _fire could have been queued already
    while (t.c.len() > 0)
        t.c.recv();

    t._mu.unlock();
    _tWheelMu->unlock();

    return canceled;
}

// when timers are fired by _tWheel.advance(), they are first popped from _tWheel and put on
// _tFiring list, so that the real firing could be done without holding _tWheelMu.
static _TimerImpl* _tFiring     = nil;
static _TimerImpl* _tFiringLast = nil;

void _TimerImpl::_queue_fire() {
    _TimerImpl& t = *this;

    t._mu.lock();
    assert(t._state == _TimerArmed);
    t._state = _TimerFiring;
    t._mu.unlock();

    t._tFiringNext = nil;
    if (_tFiring == nil)
        _tFiring = &t;
    if (_tFiringLast != nil)
        _tFiringLast->_tFiringNext = &t;
    _tFiringLast = &t;
}

static void _timer_loop_fire_queued() {
    for (_TimerImpl* t = _tFiring; t != nil;) {
        _TimerImpl* fnext = t->_tFiringNext;
        t->_tFiringNext = nil;
        t->_fire();

        t->decref(); // wheel was holding a reference to the timer
        t = fnext;
    }
    _tFiring     = nil;
    _tFiringLast = nil;
}

void _TimerImpl::_fire() {
    _TimerImpl& t = *this;

    bool fire = false;
    t._mu.lock();
    if (t._state == _TimerFiring) {  // stop could disarm the timer in the meantime
        t._state = _TimerDisarmed;
        fire = true;

        debugf("LOOP: firing @ %lu ...\n", t._tWheelEntry.scheduled_at());

        // send under ._mu so that .stop can be sure that if it sees
        // ._state = _TimerDisarmed, there is no ongoing .c send.
        if (t._f == nil)
            t.c.send(now());
    }
    t._mu.unlock();

    // call ._f not from under ._mu not to deadlock e.g. if ._f wants to reset the timer.
    if (fire && t._f != nil)
        t._f();
}

}}  // golang::time::
