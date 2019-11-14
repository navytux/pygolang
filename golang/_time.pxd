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
"""Package time mirrors Go package time.

 - `now` returns current time.
 - `sleep` pauses current task.
 - `Ticker` and `Timer` provide timers integrated with channels.
 - `tick`, `after` and `after_func` are convenience wrappers to use
   tickers and timers easily.

See also https://golang.org/pkg/time for Go time package documentation.
"""

from golang cimport chan, cbool, refptr
from libcpp cimport nullptr_t

# golang/pyx - the same as std python - represents time as float
cdef extern from * nogil:
    # XXX how to declare/share constants without C verbatim?
    """
    #ifndef _golang_time_pxd_h
    #define _golang_time_pxd_h
    # define    golang_time_second      (1.0)
    # define    golang_time_nanosecond  (1E-9 * golang_time_second)
    # define    golang_time_microsecond (1E-6 * golang_time_second)
    # define    golang_time_millisecond (1E-3 * golang_time_second)
    # define    golang_time_minute      (60   * golang_time_second)
    # define    golang_time_hour        (60   * golang_time_minute)
    #endif // _golang_time_pxd_h
    """
    const double second         "golang_time_second"
    const double nanosecond     "golang_time_nanosecond"
    const double microsecond    "golang_time_microsecond"
    const double millisecond    "golang_time_millisecond"
    const double minute         "golang_time_minute"
    const double hour           "golang_time_hour"


cdef extern from "golang/time.h" namespace "golang::time" nogil:
    void   sleep(double dt)
    double now()

    chan[double] tick(double dt)
    chan[double] after(double dt)
    Timer        after_func(double dt, ...)    # ... = func<void()>

    cppclass _Ticker:
        chan[double] c
        void stop()

    cppclass Ticker (refptr[_Ticker]):
        # Ticker.X = Ticker->X in C++.
        chan[double] c      "_ptr()->c"
        void         stop   "_ptr()->stop" ()

    Ticker new_ticker(double dt)


    cppclass _Timer:
        chan[double] c
        cbool stop()
        void  reset(double dt)

    cppclass Timer (refptr[_Timer]):
        # Timer.X = Timer->X in C++.
        chan[double] c      "_ptr()->c"
        cbool        stop   "_ptr()->stop"  ()
        void         reset  "_ptr()->reset" (double dt)

    Timer new_timer(double dt)
