# cython: language_level=2
# Copyright (C) 2021-2022  Nexedi SA and Contributors.
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
"""Package os mirrors Go package os.

 - `Signal` represents OS-level signal.

See also https://golang.org/pkg/os for Go os package documentation.
"""

#from golang cimport string        # TODO restore after golang.pyx stops to import os.pyx
from libcpp.string cimport string  # golang::string = std::string   TODO remove after ^^^

cdef extern from "golang/os.h" namespace "golang::os" nogil:
    struct Signal:
        int signo

        string String()

    Signal _Signal_from_int(int signo)

# ---- python bits ----

from cython cimport final

@final
cdef class PySignal:
    cdef Signal sig

    # PySignal.from_sig returns PySignal wrapping py/nogil-level Signal sig
    @staticmethod
    cdef PySignal from_sig(Signal sig)
