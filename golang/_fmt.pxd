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
"""Package fmt mirrors Go package fmt.

 - `sprintf` formats text into string.
 - `errorf`  formats text into error.

NOTE: with exception of %w, formatting rules are those of libc, not Go(*).

See also https://golang.org/pkg/fmt for Go fmt package documentation.

(*) errorf additionally handles Go-like %w to wrap an error similarly to
    https://blog.golang.org/go1.13-errors .
"""

from golang cimport string, error

cdef extern from "golang/fmt.h" namespace "golang::fmt" nogil:
    string sprintf(const string &format, ...)
    error  errorf (const string &format, ...)

    string sprintf(const char *format, ...)
    error  errorf (const char *format, ...)
