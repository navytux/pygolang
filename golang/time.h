#ifndef _NXD_LIBGOLANG_TIME_H
#define	_NXD_LIBGOLANG_TIME_H

// Copyright (C) 2019-2020  Nexedi SA and Contributors.
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
//
//  - `now` returns current time.
//  - `sleep` pauses current task.
//  - `Ticker` and `Timer` provide timers integrated with channels.
//  - `tick`, `after` and `after_func` are convenience wrappers to use
//    tickers and timers easily.
//
// See also https://golang.org/pkg/time for Go time package documentation.
//
//
// C-level API
//
// Subset of time package functionality is also provided via C-level API:
//
//  - `_tasknanosleep` pauses current task.
//  - `_nanotime` returns current time.


#include <golang/libgolang.h>
#include <golang/sync.h>


// ---- C-level API ----

#ifdef __cplusplus
namespace golang {
namespace time {
extern "C" {
#endif

LIBGOLANG_API void _tasknanosleep(uint64_t dt);
LIBGOLANG_API uint64_t _nanotime(void);

#ifdef __cplusplus
}}} // golang::time:: "C"
#endif


// ---- C++ API ----

#ifdef __cplusplus

// golang::time::
namespace golang {
namespace time {

// golang/pyx/c++ - the same as std python - represents time as float
constexpr double second       = 1.0;
constexpr double nanosecond   = 1E-9 * second;
constexpr double microsecond  = 1E-6 * second;
constexpr double millisecond  = 1E-3 * second;
constexpr double minute       = 60   * second;
constexpr double hour         = 60   * minute;


// sleep pauses current goroutine for at least dt seconds.
LIBGOLANG_API void sleep(double dt);

// now returns current time in seconds.
LIBGOLANG_API double now();


typedef refptr<struct _Ticker> Ticker;
typedef refptr<struct _Timer>  Timer;

// tick returns channel connected to dt ticker.
//
// Note: there is no way to stop created ticker.
// Note: for dt <= 0, contrary to Ticker, tick returns nil channel instead of panicking.
LIBGOLANG_API chan<double> tick(double dt);

// after returns channel connected to dt timer.
//
// Note: with after there is no way to stop/garbage-collect created timer until it fires.
LIBGOLANG_API chan<double> after(double dt);

// after_func arranges to call f after dt time.
//
// The function will be called in its own goroutine.
// Returned timer can be used to cancel the call.
LIBGOLANG_API Timer after_func(double dt, func<void()> f);


// new_ticker creates new Ticker that will be firing at dt intervals.
LIBGOLANG_API Ticker new_ticker(double dt);

// Ticker arranges for time events to be sent to .c channel on dt-interval basis.
//
// If the receiver is slow, Ticker does not queue events and skips them.
// Ticking can be canceled via .stop() .
struct _Ticker : object {
    chan<double> c;

private:
    double      _dt;
    sync::Mutex _mu;
    bool        _stop;

    // don't new - create only via new_ticker()
private:
    _Ticker();
    ~_Ticker();
    friend Ticker new_ticker(double dt);
public:
    LIBGOLANG_API void decref();

public:
    // stop cancels the ticker.
    //
    // It is guaranteed that ticker channel is empty after stop completes.
    LIBGOLANG_API void stop();

private:
    void _tick();
};


// new_timer creates new Timer that will fire after dt.
LIBGOLANG_API Timer new_timer(double dt);

// Timer arranges for time event to be sent to .c channel after dt time.
//
// The timer can be stopped (.stop), or reinitialized to another time (.reset).
struct _Timer : object {
    chan<double> c;

private:
    func<void()> _f;

    sync::Mutex  _mu;
    double       _dt;  // +inf - stopped, otherwise - armed
    int          _ver; // current timer was armed by n'th reset

    // don't new - create only via new_timer() & co
private:
    _Timer();
    ~_Timer();
    friend Timer _new_timer(double dt, func<void()> f);
public:
    LIBGOLANG_API void decref();

public:
    // stop cancels the timer.
    //
    // It returns:
    //
    //   False: the timer was already expired or stopped,
    //   True:  the timer was armed and canceled by this stop call.
    //
    // Note: contrary to Go version, there is no need to drain timer channel
    // after stop call - it is guaranteed that after stop the channel is empty.
    //
    // Note: similarly to Go, if Timer is used with function - it is not
    // guaranteed that after stop the function is not running - in such case
    // the caller must explicitly synchronize with that function to complete.
    LIBGOLANG_API bool stop();

    // reset rearms the timer.
    //
    // the timer must be either already stopped or expired.
    LIBGOLANG_API void reset(double dt);

private:
    void _fire(double dt, int ver);
};


}}   // golang::time::
#endif  // __cplusplus

#endif	// _NXD_LIBGOLANG_TIME_H
