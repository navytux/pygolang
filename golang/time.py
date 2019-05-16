# -*- coding: utf-8 -*-
# Copyright (C) 2019  Nexedi SA and Contributors.
#                     Kirill Smelkov <kirr@nexedi.com>
#
# This program is free software: you can Use, Study, Modify and Redistribute
# it under the terms of the GNU General Public License version 3, or (at your
# option) any later version, as published by the Free Software Foundation.
#
# You can also Link and Combine this program with other software covered by
# the terms of any of the Free Software licenses or any of the Open Source
# Initiative approved licenses and Convey the resulting work. Corresponding
# source of such a combination shall include the source code for all other
# software used.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# See COPYING file for full licensing terms.
# See https://www.nexedi.com/licensing for rationale and options.
"""Package time mirrors Go package time.

See the following link about Go time package:

    https://golang.org/pkg/time
"""

from __future__ import print_function, absolute_import

import time as _time
from golang import go, chan, select, default, nilchan, panic
import threading

# golang/py - the same as std python - represents time as float
second      = 1.0
nanosecond  = 1E-9 * second
microsecond = 1E-6 * second
millisecond = 1E-3 * second
minute      = 60   * second
hour        = 60   * minute

sleep   = _time.sleep
now     = _time.time


# ---- timers ----
# FIXME timers are implemented very inefficiently - each timer currently consumes a goroutine.

# tick returns channel connected to dt ticker.
#
# Note: there is no way to stop created ticker.
# Note: for dt <= 0, contrary to Ticker, tick returns nilchan instead of panicking.
def tick(dt):   # -> chan time
    if dt <= 0:
        return nilchan
    return Ticker(dt).c

# after returns channel connected to dt timer.
#
# Note: with after there is no way to stop/garbage-collect created timer until it fires.
def after(dt):  # -> chan time
    return Timer(dt).c

# after_func arranges to call f after dt time.
#
# The function will be called in its own goroutine.
# Returned timer can be used to cancel the call.
def after_func(dt, f):  # -> Timer
    return Timer(dt, f=f)


# Ticker arranges for time events to be sent to .c channel on dt-interval basis.
#
# If the receiver is slow, Ticker does not queue events and skips them.
# Ticking can be canceled via .stop() .
class Ticker(object):
    def __init__(self, dt):
        if dt <= 0:
            panic("ticker: dt <= 0")
        self.c      = chan(1)   # 1-buffer -- same as in Go
        self._dt    = dt
        self._mu    = threading.Lock()
        self._stop  = False
        go(self._tick)

    # stop cancels the ticker.
    #
    # It is guaranteed that ticker channel is empty after stop completes.
    def stop(self):
        with self._mu:
            self._stop = True

            # drain what _tick could have been queued already
            while len(self.c) > 0:
                self.c.recv()

    def _tick(self):
        while 1:
            # XXX adjust for accumulated error δ?
            sleep(self._dt)

            with self._mu:
                if self._stop:
                    return

                # send from under ._mu so that .stop can be sure there is no
                # ongoing send while it drains the channel.
                select(
                    default,
                    (self.c.send, now()),
                )


# Timer arranges for time event to be sent to .c channel after dt time.
#
# The timer can be stopped (.stop), or reinitialized to another time (.reset).
#
# If func f is provided - when the timer fires f is called in its own goroutine
# instead of event being sent to channel .c .
class Timer(object):
    def __init__(self, dt, f=None):
        self._f     = f
        self.c      = chan(1) if f is None else nilchan
        self._mu    = threading.Lock()
        self._dt    = None  # None - stopped, float - armed
        self._ver   = 0     # current timer was armed by n'th reset
        self.reset(dt)

    # stop cancels the timer.
    #
    # It returns:
    #
    #   False: the timer was already expired or stopped,
    #   True:  the timer was armed and canceled by this stop call.
    #
    # Note: contrary to Go version, there is no need to drain timer channel
    # after stop call - it is guaranteed that after stop the channel is empty.
    #
    # Note: similarly to Go, if Timer is used with function - it is not
    # guaranteed that after stop the function is not running - in such case
    # the caller must explicitly synchronize with that function to complete.
    def stop(self): # -> canceled
        with self._mu:
            if self._dt is None:
                canceled = False
            else:
                self._dt  = None
                self._ver += 1
                canceled = True

            # drain what _fire could have been queued already
            while len(self.c) > 0:
                self.c.recv()

            return canceled

    # reset rearms the timer.
    #
    # the timer must be either already stopped or expired.
    def reset(self, dt):
        with self._mu:
            if self._dt is not None:
                panic("Timer.reset: the timer is armed; must be stopped or expired")
            self._dt  = dt
            self._ver += 1
            go(self._fire, dt, self._ver)


    def _fire(self, dt, ver):
        sleep(dt)
        with self._mu:
            if self._ver != ver:
                return  # the timer was stopped/resetted - don't fire it
            self._dt = None

            # send under ._mu so that .stop can be sure that if it sees
            # ._dt = None, there is no ongoing .c send.
            if self._f is None:
                self.c.send(now())
                return

        # call ._f not from under ._mu not to deadlock e.g. if ._f wants to reset the timer.
        self._f()
