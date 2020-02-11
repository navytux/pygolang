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
"""_errors.pyx implements errors.pyx - see _errors.pxd for package overview."""

from __future__ import print_function, absolute_import

from golang cimport pyerror, nil, topyexc
from golang import b as pyb
from golang cimport errors

# Taking both .Unwrap() and .__cause__ into account
#
# Contrary to Go and Pyx/C++ cases, in Python errors could link to each other
# by both .Unwrap() and .__cause__ . Below we show that both error links have
# to be taken into account when building an error's chain, and how:
#
# Consider the following cases
#
#     1. X -> X
#     2. X -> error
#     3. error -> X
#     4. error -> error
#
# where
#
#     "->" means link via .__cause__,
#     X     - exception that does not provide .Unwrap()
#     error - exception that provides .Unwrap()
#
# 1: Since the cause is explicit we want errors.Unwrap to follow "->" link,
#    so that e.g. errors.Is works correctly.
#
# 2: The same.
#
# 3: Consider e.g.
#
#     e1 w→ e2 w→ e3                  w→ denotes what .Unwrap() returns
#     |                               -> denotes .__cause__
#     v
#     X
#
#    this picture is a result of
#
#     try:
#         # call something that raises regular exc X
#     except X:
#         err = dosmth_pygo()
#         raise err from x
#
#    due to the logic in code we a) want to keep X in unwrap sequence of err
#    (it was explicitly specified as cause), and b) we want X to be in the
#    end of unwrap sequence of err, because due to the logic it is the most
#    inner cause:
#
#     e1 w→ e2 w→ e3
#     |            w
#     v            |
#     X ← ← ← ← ← ←
#
# 4: Consider e.g.
#
#     e11 w→ e12 w→ e13
#     |
#     v
#     e21 w→ e22
#
#    Similarly to 3 we want err2 to be kept in unwrap sequence of err1 and to
#    be appended there into tail:
#
#     e11 w→ e12 w→ e13
#     | ← ← ← ← ← ← ← w
#     v↓
#     e21 w→ e22
#
# 1-4 suggest the following rules: let U(e) be the list with full error chain
# of e, starting from e itself. For example for `err = e1 w→ e2 w→ e3`,
# `U(err) = [e1, e2, e3]`
#
# we can deduce recursive formula for U based on 1-4:
#
# - U(nil) = []                                           ; obvious
#
# - for e:                U(e) = [e]                      ; obvious
#     .w = nil
#     .__cause__ = nil
#
# - for e:                U(e) = [e] + U(e.w)             ; regular go-style wrapping
#     .w != nil
#     .__cause__ = nil
#
# - for e:                U(e) = [e] + U(e.__cause__)     ; cases 1 & 2
#     .w = nil
#     .__cause__ != nil
#
# - for e:                U(e) = [e] + U(e.w) + U(e.__cause__)    ; ex. cases 3 & 4
#     .w != nil
#     .__cause__ != nil
#
# the formula for cases 3 & 4 is the general one and works for all cases:
#
#     U(nil) = []
#     U(e)   = [e] + U(e.w) + U(e.__cause__)
#
#
# e.g. consider how it works for:
#
#     e1 w→ e2 w→ e3
#     |     |      w
#     v     v      |
#     X1← ← X2← ← ←
#
# U(e1) = [e1] + U(e2) + U(X1)
#       = [e1] + {[e2] + U(e3) + U(X2)} + [X1]
#       = [e1] + {[e2] + [e3] + [X2]} + [X1]
#       = [e1, e2, e3, X2, X1]
#
# --------
#
# Implementation: with errors.Unwrap we cannot use U directly to implement
# unwrapping because it requires to keep unwrapping iterator state and
# errors.Unwrap API returns just an error instance, nothing more. For this
# reason python version of errors package, does not expose errors.Unwrap, and
# internally uses errors._UnwrapIter, which returns iterator through an
# error's error chain.


def pyNew(text): # -> error
    """New creates new error with provided text."""
    return pyerror.from_error(errors_New_pyexc(pyb(text)))


def _pyUnwrapIter(err): # -> iter(error)
    """_UnwrapIter returns iterator through err's error chain.

       This iteration takes both .Unwrap() and .__cause__ into account.
       See "Taking both .Unwrap() and .__cause__ into account" in internal overview.
    """
    if err is None:
        return
    if not isinstance(err, BaseException):
        raise TypeError("errors.UnwrapIter: err is not exception: type(err)=%r" % type(err))

    cdef pyerror pye
    cdef error   e

    # + U(e.w)
    if type(err) is not pyerror:
        # err is python-level error (pyerror-based or just BaseException child)
        eunwrap = getattr(err, 'Unwrap', _missing)
        pyw = None
        if eunwrap is not _missing:
            pyw = eunwrap()
        if pyw is not None:
            yield pyw
            for _ in _pyUnwrapIter(pyw):
                yield _
    else:
        # err is wrapper around C-level error
        pye = err
        e   = pye.err
        while 1:
            e = errors_Unwrap_pyexc(e)
            if e == nil:
                break
            yield pyerror.from_error(e)

    # + U(e.__cause__)
    pycause    = getattr(err, '__cause__', None)
    if pycause is not None:
        yield pycause
        for _ in _pyUnwrapIter(pycause):
            yield _


def pyIs(err, target): # -> bool
    """Is returns whether target matches any error in err's error chain."""

    # err and target must be exception or None
    if not (isinstance(err, BaseException) or err is None):
        raise TypeError("errors.Is: err is not exception or None: type(err)=%r" % type(err))
    if not (isinstance(target, BaseException) or target is None):
        raise TypeError("errors.Is: target is not exception or None: type(target)=%r" % type(target))

    if target is None:
        return (err is None)

    wit = _pyUnwrapIter(err)
    while 1:
        if err is None:
            return False

        if type(err) is type(target):
            if err == target:
                return True

        err = next(wit, None)


# ---- misc ----

cdef _missing = object()

cdef nogil:

    error errors_New_pyexc(const char* text)            except +topyexc:
        return errors.New(text)

    error errors_Unwrap_pyexc(error err)                except +topyexc:
        return errors.Unwrap(err)
