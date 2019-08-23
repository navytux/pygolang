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

See the following link about Go time package:

    https://golang.org/pkg/time
"""

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


cdef extern from "golang/libgolang.h" namespace "golang::time" nogil:
    void   sleep(double dt)
    double now()
