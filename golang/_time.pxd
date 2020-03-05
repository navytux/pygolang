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
"""Package time mirrors Go package time.

 - `now` returns current time.
 - `sleep` pauses current task.
 - `Ticker` and `Timer` provide timers integrated with channels.
 - `tick`, `after` and `after_func` are convenience wrappers to use
   tickers and timers easily.

See also https://golang.org/pkg/time for Go time package documentation.
"""

from golang cimport chan, cbool, refptr

cdef extern from "golang/time.h" namespace "golang::time" nogil:
    const double second
    const double nanosecond
    const double microsecond
    const double millisecond
    const double minute
    const double hour

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
