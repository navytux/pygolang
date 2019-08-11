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
"""XXX"""   # XXX

from libc.stdint cimport uint64_t

cdef extern from "golang/libgolang.h" namespace "golang" nogil:
    void     _tasknanosleep(uint64_t dt)
    uint64_t _nanotime()

from libc.stdio cimport printf  # XXX temp

# XXX doc
cdef double now() nogil:
    printf("time.now ...\n")
    cdef uint64_t t_ns = _nanotime()
    cdef double t_s = t_ns * 1E-9
    printf("\ttime.now -> %.1f\n", t_s)
    return t_s

# XXX doc
cdef void sleep(double dt) nogil:
    cdef uint64_t dt_ns = <uint64_t>(dt * 1E9)    # XXX overflow
    printf("time.sleep %.1f   (%luns)\n", dt, dt_ns)
    _tasknanosleep(dt_ns)
    printf("\ttime.sleep woke up\n")


def pynow(): # -> t
    return now_pyexc()

def pysleep(double dt):
    with nogil:
        sleep_pyexc(dt)


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
