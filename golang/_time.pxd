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

# golang/pyx - the same as std python - represents time as float
DEF second      = 1.0
DEF nanosecond  = 1E-9 * second
DEF microsecond = 1E-6 * second
DEF millisecond = 1E-3 * second
DEF minute      = 60   * second
DEF hour        = 60   * minute


# XXX doc
cdef double now() nogil:
    # XXX

# XXX doc
cdef void sleep(double dt) nogil:
    # XXX


def pynow(): # -> t
    return now_pyexc()

def pysleep(double dt):
    sleep_pyexc(dt)


# ---- misc ----
cdef double now_pyexc()             nogil except +topyexc:
    return now()
cdef void sleep_pyexc(double dt)    nogil except +topyexc:
    sleep(dt)
