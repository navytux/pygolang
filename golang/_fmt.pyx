# -*- coding: utf-8 -*-
# cython: language_level=2
# cython: c_string_type=str, c_string_encoding=utf8
# distutils: language=c++
#
# Copyright (C) 2020  Nexedi SA and Contributors.
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
"""_fmt.pyx implements fmt.pyx - see _fmt.pxd for package overview."""

from __future__ import print_function, absolute_import

from golang cimport pyerror
from golang cimport errors, fmt

# _PyWrapError is the pyerror created by pyErrorf("...: %w", pyerr), for case
# when pyerr is general python error - instead of being just pyerror wrapper
# around raw C-level error.
cdef class _PyWrapError(pyerror):
    cdef str    _prefix
    cdef object _errSuffix

    def __cinit__(_PyWrapError pywerr, str prefix, object errSuffix):
        pywerr._prefix = prefix
        pywerr._errSuffix = errSuffix

    def Unwrap(_PyWrapError pywerr): # -> error | None
        return pywerr._errSuffix
    def Error(_PyWrapError pywerr): # -> str
        esuff = pywerr._errSuffix
        if esuff is None:
            esuff = "%!w(<None>)"   # mimic go
        return "%s: %s" % (pywerr._prefix, esuff)


def pyErrorf(str format, *argv): # -> error
    """Errorf formats text into error.

       format suffix ": %w" is additionally handled as in Go with
       `Errorf("... : %w", ..., err)` creating error that can be unwrapped back to err.
    """
    xpyerr = None
    withW  = False
    if format.endswith(": %w"):
        withW = True
        format = format[:-4]
        xpyerr = argv[-1]
        argv   = argv[:-1]

    # NOTE: this will give TypeError  if format vs args is not right.
    # NOTE: this will give ValueError if %w is used inside suffix-stripped format.
    prefix = format % argv

    if not withW:
        return pyerror.from_error(errors.New(prefix))

    if not (isinstance(xpyerr, BaseException) or xpyerr is None):
        raise TypeError("fmt.Errorf: lastarg to wrap is not error: type(argv[-1])=%r" % type(xpyerr))

    # xpyerr is arbitrary exception class - not a wrapper around C-level error object
    if type(xpyerr) is not pyerror:
        return _PyWrapError(prefix, xpyerr)

    # xpyerr is wrapper around C-level error object
    cdef pyerror pyerr = xpyerr
    return pyerror.from_error(fmt.errorf("%s: %w", <const char *>prefix, pyerr.err))
