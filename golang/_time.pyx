# cython: language_level=2
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
"""_time.pyx implements time.pyx - see _time.pxd for package overview."""

from __future__ import print_function, absolute_import

from golang cimport pychan
from golang cimport sync
from libc.math cimport INFINITY
from cython cimport final

from golang import go as pygo, select as pyselect, default as pydefault, nilchan as pynilchan, panic as pypanic


def pynow(): # -> t
    return now_pyexc()

def pysleep(double dt):
    with nogil:
        sleep_pyexc(dt)


# ---- timers ----
# FIXME timers are implemented very inefficiently - each timer currently consumes a goroutine.

# tick returns channel connected to dt ticker.
#
# Note: there is no way to stop created ticker.
# Note: for dt <= 0, contrary to Ticker, tick returns nilchan instead of panicking.
def tick(double dt):    # -> chan time
    if dt <= 0:
        return pynilchan
    return Ticker(dt).c

# after returns channel connected to dt timer.
#
# Note: with after there is no way to stop/garbage-collect created timer until it fires.
def after(double dt):   # -> chan time
    return Timer(dt).c

# after_func arranges to call f after dt time.
#
# The function will be called in its own goroutine.
# Returned timer can be used to cancel the call.
def after_func(double dt, f):  # -> Timer
    return Timer(dt, f=f)


# Ticker arranges for time events to be sent to .c channel on dt-interval basis.
#
# If the receiver is slow, Ticker does not queue events and skips them.
# Ticking can be canceled via .stop() .
@final
cdef class Ticker:
    cdef readonly pychan  c

    cdef double      _dt
    cdef sync.Mutex  _mu
    cdef bint        _stop

    def __init__(Ticker self, double dt):
        if dt <= 0:
            pypanic("ticker: dt <= 0")
        self.c      = pychan(1) # 1-buffer -- same as in Go
        self._dt    = dt
        self._stop  = False
        pygo(self._tick)

    # stop cancels the ticker.
    #
    # It is guaranteed that ticker channel is empty after stop completes.
    def stop(Ticker self):
        self._mu.lock()
        self._stop = True

        # drain what _tick could have been queued already
        while len(self.c) > 0:
            self.c.recv()
        self._mu.unlock()

    def _tick(Ticker self):
        while 1:
            # XXX adjust for accumulated error δ?
            pysleep(self._dt)

            self._mu.lock()
            if self._stop:
                self._mu.unlock()
                return

            # send from under ._mu so that .stop can be sure there is no
            # ongoing send while it drains the channel.
            pyselect(
                pydefault,
                (self.c.send, pynow()),
            )
            self._mu.unlock()


# Timer arranges for time event to be sent to .c channel after dt time.
#
# The timer can be stopped (.stop), or reinitialized to another time (.reset).
#
# If func f is provided - when the timer fires f is called in its own goroutine
# instead of event being sent to channel .c .
@final
cdef class Timer:
    cdef readonly pychan  c

    cdef object     _f
    cdef sync.Mutex _mu
    cdef double     _dt   # +inf - stopped, otherwise - armed
    cdef int        _ver  # current timer was armed by n'th reset

    def __init__(Timer self, double dt, f=None):
        self._f     = f
        self.c      = pychan(1) if f is None else pynilchan
        self._dt    = INFINITY
        self._ver   = 0
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
    def stop(Timer self): # -> canceled
        self._mu.lock()

        if self._dt == INFINITY:
            canceled = False
        else:
            self._dt  = INFINITY
            self._ver += 1
            canceled = True

        # drain what _fire could have been queued already
        while len(self.c) > 0:
            self.c.recv()

        self._mu.unlock()
        return canceled

    # reset rearms the timer.
    #
    # the timer must be either already stopped or expired.
    def reset(Timer self, double dt):
        self._mu.lock()
        if self._dt != INFINITY:
            self._mu.unlock()
            pypanic("Timer.reset: the timer is armed; must be stopped or expired")
        self._dt  = dt
        self._ver += 1
        pygo(self._fire, dt, self._ver)
        self._mu.unlock()


    def _fire(Timer self, double dt, int ver):
        pysleep(dt)
        self._mu.lock()
        if self._ver != ver:
            self._mu.unlock()
            return  # the timer was stopped/resetted - don't fire it
        self._dt = INFINITY

        # send under ._mu so that .stop can be sure that if it sees
        # ._dt = INFINITY, there is no ongoing .c send.
        if self._f is None:
            self.c.send(pynow())
            self._mu.unlock()
            return
        self._mu.unlock()

        # call ._f not from under ._mu not to deadlock e.g. if ._f wants to reset the timer.
        self._f()


# ---- misc ----
pysecond        = second
pynanosecond    = nanosecond
pymicrosecond   = microsecond
pymillisecond   = millisecond
pyminute        = minute
pyhour          = hour

from golang cimport topyexc

cdef double now_pyexc()             nogil except +topyexc:
    return now()
cdef void sleep_pyexc(double dt)    nogil except +topyexc:
    sleep(dt)
