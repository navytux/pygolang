# cython: language_level=2
# Copyright (C) 2019-2020  Nexedi SA and Contributors.
#                          Kirill Smelkov <kirr@nexedi.com>
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

from golang cimport nil, pychan, topyexc
from golang cimport sync
from golang.pyx cimport runtime
from cpython cimport PyObject
from cython cimport final


def pynow(): # -> t
    return now_pyexc()

def pysleep(double dt):
    with nogil:
        sleep_pyexc(dt)


# ---- timers ----

# tick returns channel connected to dt ticker.
#
# Note: there is no way to stop created ticker.
# Note: for dt <= 0, contrary to Ticker, tick returns nil channel instead of panicking.
def pytick(double dt):  # -> chan time
    return pychan.from_chan_double( tick(dt) )

# after returns channel connected to dt timer.
#
# Note: with after there is no way to stop/garbage-collect created timer until it fires.
def pyafter(double dt): # -> chan time
    return pychan.from_chan_double( after(dt) )

# after_func arranges to call f after dt time.
#
# The function will be called in its own goroutine.
# Returned timer can be used to cancel the call.
def pyafter_func(double dt, f):  # -> PyTimer
    return PyTimer(dt, f=f)


# Ticker arranges for time events to be sent to .c channel on dt-interval basis.
#
# If the receiver is slow, Ticker does not queue events and skips them.
# Ticking can be canceled via .stop() .
@final
cdef class PyTicker:
    cdef Ticker   tx
    cdef readonly pychan  c # pychan wrapping tx.c

    def __init__(PyTicker pytx, double dt):
        with nogil:
            pytx.tx = new_ticker_pyexc(dt)
        pytx.c = pychan.from_chan_double( pytx.tx.c )

    def __dealloc__(PyTicker pytx):
        pytx.tx = nil

    # stop cancels the ticker.
    #
    # It is guaranteed that ticker channel is empty after stop completes.
    def stop(PyTicker pytx):
        with nogil:
            ticker_stop_pyexc(pytx.tx)


# Timer arranges for time event to be sent to .c channel after dt time.
#
# The timer can be stopped (.stop), or reinitialized to another time (.reset).
#
# If func f is provided - when the timer fires f is called in its own goroutine
# instead of event being sent to channel .c .
@final
cdef class PyTimer:
    cdef Timer    t
    cdef readonly pychan  c # pychan wrapping t.c

    def __init__(PyTimer pyt, double dt, f=None):
        with nogil:
            if f is None:
                pyt.t = new_timer_pyexc(dt)
            else:
                pyt.t = _new_timer_pyfunc_pyexc(dt, <PyObject *>f)
        pyt.c = pychan.from_chan_double( pyt.t.c )

    def __dealloc__(PyTimer pyt):
        pyt.t = nil

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
    def stop(PyTimer pyt): # -> canceled
        with nogil:
            canceled = timer_stop_pyexc(pyt.t)
        return canceled

    # reset rearms the timer.
    #
    # the timer must be either already stopped or expired.
    def reset(PyTimer pyt, double dt):
        with nogil:
            timer_reset_pyexc(pyt.t, dt)


# ---- misc ----
pysecond        = second
pynanosecond    = nanosecond
pymicrosecond   = microsecond
pymillisecond   = millisecond
pyminute        = minute
pyhour          = hour

cdef nogil:

    double now_pyexc()                                      except +topyexc:
        return now()
    void sleep_pyexc(double dt)                             except +topyexc:
        sleep(dt)

    Ticker new_ticker_pyexc(double dt)                      except +topyexc:
        return new_ticker(dt)
    void ticker_stop_pyexc(Ticker tx)                       except +topyexc:
        tx.stop()
    Timer new_timer_pyexc(double dt)                        except +topyexc:
        return new_timer(dt)
    Timer _new_timer_pyfunc_pyexc(double dt, PyObject *pyf) except +topyexc:
        # NOTE C++ implicitly casts func<void()> <- func<error()>
        # XXX  error (= Py Exception) -> exit program with traceback (same as in go) ?
        return after_func(dt, runtime.PyFunc(pyf))

    cbool timer_stop_pyexc(Timer t)                         except +topyexc:
        return t.stop()
    void timer_reset_pyexc(Timer t, double dt)              except +topyexc:
        t.reset(dt)
