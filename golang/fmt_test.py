# -*- coding: utf-8 -*-
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

from __future__ import print_function, absolute_import

from golang import error
from golang import errors, fmt, _fmt
from golang.golang_test import import_pyx_tests
from golang.errors_test import Unwrap1
from pytest import raises

import_pyx_tests("golang._fmt_test")


# verify fmt.Errorf with focus on %w (error chaining).
# the rest of formatting is served by built-in python %.
def test_errorf():
    e = fmt.Errorf("abc")
    assert type(e) is error
    assert e.Error()        == "abc"
    assert Unwrap1(e)       is None

    e = fmt.Errorf("hello %d world %s", 123, "мир")
    assert type(e) is error
    assert e.Error()        == "hello 123 world мир"
    assert Unwrap1(e)       is None

    # %w with !exception
    with raises(TypeError): fmt.Errorf(": %w", 1)
    with raises(TypeError): fmt.Errorf(": %w", object())

    # errorf with chaining
    e = errors.New("problem")
    w = fmt.Errorf("%s %s: %w", "op", "file", e)
    assert type(w) is error
    assert w.Error()        == "op file: problem"
    assert Unwrap1(w)       == e
    assert errors.Is(w, e)  == True

    w = fmt.Errorf("%s %s: %s", "op", "file", e)
    assert type(w) is error
    assert w.Error()        == "op file: problem"
    assert Unwrap1(w)       is None
    assert errors.Is(w, e)  == False

    # chaining to !error
    e = RuntimeError("abc")
    w = fmt.Errorf("zzz: %w", e)
    assert type(w) is _fmt._PyWrapError
    assert w.Error()        == "zzz: abc"
    assert Unwrap1(w)       is e    # NOTE is
    assert errors.Is(w, e)  == True
    assert Unwrap1(e)       is None

    # chaining to !error with .Unwrap
    class MyError(Exception):
        def __init__(myerr, op, path, err):
            super(MyError, myerr).__init__(op, path, err)
            myerr.op    = op
            myerr.path  = path
            myerr.err   = err

        def Unwrap(myerr):  return myerr.err
        def __str__(myerr): return "myerror %s %s: %s" % (myerr.op, myerr.path, myerr.err)
        # NOTE: no .Error provided

    e1 = KeyError("not found")
    e  = MyError("load", "zzz", e1)
    w  = fmt.Errorf("yyy: %w", e)
    assert type(w) is _fmt._PyWrapError
    with raises(AttributeError): e.Error
    assert str(e)           == "myerror load zzz: 'not found'"
    assert w.Error()        == "yyy: myerror load zzz: 'not found'"
    assert str(w)           == "yyy: myerror load zzz: 'not found'"
    assert Unwrap1(w)       is e    # NOTE is
    assert Unwrap1(e)       is e1   # NOTE is
    assert Unwrap1(e1)      is None
    assert errors.Is(w, e)  == True
    assert errors.Is(w, e1) == True
    assert errors.Is(e, e1) == True

    # %w with nil error
    e = fmt.Errorf("aaa: %w", None)
    assert type(e) is _fmt._PyWrapError
    assert e.Error()        == "aaa: %!w(<None>)"
    assert str(e)           == "aaa: %!w(<None>)"
    assert Unwrap1(e)       is None

    # multiple %w or ": %w" not as suffix -> ValueError
    with raises(ValueError): fmt.Errorf("%w", e)
    with raises(ValueError): fmt.Errorf(":%w", e)
    with raises(ValueError): fmt.Errorf("a %w : %w", e, e)
    with raises(ValueError): fmt.Errorf("%w hi", e)
