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
"""Package errors mirrors Go package errors.

 - `New` creates new error with provided text.
 - `Unwrap` tries to extract wrapped error.
 - `Is` tests whether an item in error's chain matches target.

See also https://golang.org/pkg/errors for Go errors package documentation.
See also https://blog.golang.org/go1.13-errors for error chaining overview.
"""

from golang cimport error, string, cbool

cdef extern from "golang/errors.h" namespace "golang::errors" nogil:
    error New(const string& text)
    error Unwrap(error err)
    cbool Is(error err, error target)
