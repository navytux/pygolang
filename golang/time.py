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

sleep   = _time.sleep
now     = _time.time

# tick ... XXX
def tick(dt):   # -> chan time
    if dt <= 0:
        return nilchan
    return Ticker(dt).c


# after ... XXX
def after(dt):  # -> chan time
    return Timer(dt).c

# after_func ... XXX
def after_func(dt, f):  # -> Timer
    t = Timer(dt, f=f)
    return t


# XXX doc
class Ticker(object):
    def __init__(self, dt):
        if dt <= 0:
            panic("ticker: dt <= 0")
        self.c      = chan(1)   # 1-buffer -- same as in Go
        self._dt    = dt
        self._mu    = threading.Lock()
        self._stop  = False
        go(self._tick)

    def stop(self):
        with self._mu:
            self._stop = True

    def _tick(self):
        while 1:
            sleep(self._dt)
            with self._mu:
                if self._stop:
                    return
            select(
                default,
                (self.c.send, now()),
            )


# XXX doc
class Timer(object):
    def __init__(self, dt, f=None):
        self._f     = f
        self.c      = chan(1) if f is None else nilchan
        self._mu    = threading.Lock()
        self._dt    = None  # None - stopped, float - armed
        self._ver   = 0     # current timer was armed by n'th reset
        self.reset(dt)

    def stop(self): # -> changed_to_stopped bool
        with self._mu:
            if self._dt is None:
                return False
            self._dt  = None
            self._ver += 1
            return True

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

        if self._f is None:
            self.c.send(now())
        else:
            self._f()
