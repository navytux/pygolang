# -*- coding: utf-8 -*-
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

from __future__ import print_function, absolute_import

from golang import error, b
from golang import errors, _errors
from golang.golang_test import import_pyx_tests
from golang._errors_test import pyerror_mkchain as error_mkchain
from pytest import raises

import_pyx_tests("golang._errors_test")


# assertEeq asserts that `e1 == e2`, `not (e1 != e2)`, `hash(e1) == hash(e2)`,
# and symmetrically.
def assertEeq(e1, e2):
    assert e1 == e2
    assert e2 == e1
    assert not (e1 != e2)
    assert not (e2 != e1)
    assert hash(e1) == hash(e2)
    assert hash(e2) == hash(e1)

# assertEne asserts that `e1 != e2`, `not (e1 == e2)` and symmetrically.
def assertEne(e1, e2):
    assert e1 != e2
    assert e2 != e1
    assert not (e1 == e2)
    assert not (e2 == e1)

    # cannot - generally speaking there could be hash collisions
    #assert hash(e1) != hash(e2)


# EError is custom error class that inherits from error.
class EError(error):
    def __init__(myerr, op, ret):
        myerr.op  = op
        myerr.ret = ret

    def Error(myerr): return "my %s: %s" % (myerr.op, myerr.ret)
    # no .Unwrap()

    # NOTE error provides good __eq__ and __hash__ out of the box.


# EErrorWrap is custom error class that inherits from error and provides .Unwrap()
class EErrorWrap(error):
    def __init__(myw, text, err):
        myw.text = text
        myw.err  = err

    def Error(myw):  return "%s: %s" % (myw.text, myw.err)
    def Unwrap(myw): return myw.err

# XWrap is custom error class that provides .Unwrap(), but does not inherit
# from error, nor provides .Error().
class XWrap(BaseException): # NOTE does not inherit from error
    def __init__(xw, text, err):
        xw.text = text
        xw.err  = err

    def Unwrap(xw):  return xw.err
    def __str__(xw): return "%s: %s" % (xw.text, xw.err)
    # no .Error()

    def __eq__(a, b):
        return (type(a) is type(b)) and \
                (a.text == b.text) and (a.err == b.err)


# XExc is custom error class that does not inherit from error, nor provides
# .Error() nor .Unwrap().
class XExc(Exception): # NOTE does not inherit from error
    def __init__(xerr, text):
        xerr.text = text
    def __str__(xerr):  return xerr.text
    def __repr__(xerr): return 'XExc("%s")' % xerr.text
    # no .Error()
    # no .Unwrap()

    def __eq__(a, b):
        return (type(a) is type(b)) and \
                (a.text == b.text)


# Unwrap1(e) is approximate for `errors.Unwrap(e)` in Go.
def Unwrap1(e):
    wit = _errors._pyUnwrapIter(e)
    return next(wit, None)


# test for golang.error class.
def test_error():
    assert error_mkchain([]) is None

    e = error_mkchain(["abc"])
    assert type(e)    is error
    assert e.Error()  == "abc"
    assert str(e)     == "abc"
    assert repr(e).endswith(' error="abc">')
    assert e.Unwrap() is None
    assertEeq(e, e)

    e1 = e
    e = error_mkchain(["привет", "abc"])
    assert type(e)    is error
    assert e.Error()  == "привет: abc"
    assert str(e)     == "привет: abc"
    assert repr(e).endswith(' error="привет: abc">')
    e1_ = e.Unwrap()
    assert type(e1_) is type(e1)
    assertEeq(e1_, e1)
    assert e1_.Unwrap() is None
    assertEeq(e, e)
    assertEne(e, e1)

    e2 = e

    # create an error from py via error() call
    with raises(ValueError): error()
    with raises(ValueError): error("hello", "world")
    for x in ["hello мир", u"hello мир", b("hello мир")]:
        e = error(x)
        assert type(e)    is error
        assert e.Error()  == "hello мир"
        assert str(e)     == "hello мир"
        assert repr(e).endswith(' error="hello мир">')
        assert e.Unwrap() is None
        assertEeq(e, e)

    # create an error from py via error subclass
    class EErr(error): pass
    m = EErr("abc")
    assertEeq(m, m)
    assertEne(m, error("abc"))  # EErr("abc") != error("abc")

    epy = EError("load", 3)
    assert type(epy)    is EError
    assert epy.Error()  == "my load: 3"
    assert str(epy)     == "my load: 3"
    assert repr(epy)    == "golang.errors_test.EError('load', 3)"
    assert epy.Unwrap() is None
    assertEeq(epy, epy)
    assertEeq(epy, EError("load", 3))
    assertEne(epy, EError("load", 4))

    wpy = EErrorWrap("mywrap", epy)
    assert type(wpy)    is EErrorWrap
    assert wpy.Error()  == "mywrap: my load: 3"
    assert str(wpy)     == "mywrap: my load: 3"
    assert repr(wpy)    == "golang.errors_test.EErrorWrap('mywrap', golang.errors_test.EError('load', 3))"
    assert wpy.Unwrap() is epy
    assert epy.Unwrap() is None

    epy = RuntimeError("zzz")
    wpy = EErrorWrap("qqq", epy)
    assert type(wpy) is EErrorWrap
    assert wpy.Error()  == "qqq: zzz"
    assert str(wpy)     == "qqq: zzz"
    assert repr(wpy)    == "golang.errors_test.EErrorWrap('qqq', %r)" % epy
    assert wpy.Unwrap() is epy
    with raises(AttributeError): epy.Unwrap


def test_new():
    E = errors.New

    for x in ["мир", u"мир", b("мир")]:
        err = E(x)
        assert type(err) is error
        assertEeq(err, E("мир"))
        assertEne(err, E("def"))

        assertEeq(err, error("мир"))
        assertEeq(err, error(u"мир"))
        assertEeq(err, error(b("мир")))

    with raises(TypeError):
        E(1)


# verify Unwrap for simple linear cases.
def test_unwrap():
    E  = errors.New
    Ec = error_mkchain

    # err must be exception or None
    assert Unwrap1(None) is None
    assert Unwrap1(BaseException()) is None
    with raises(TypeError): Unwrap1(1)
    with raises(TypeError): Unwrap1(object())

    ewrap = Ec(["abc", "def", "zzz"])
    e1 = Unwrap1(ewrap)
    assertEeq(e1, Ec(["def", "zzz"]))
    e2 = Unwrap1(e1)
    assertEeq(e2, E("zzz"))
    assert Unwrap1(e2) is None

    # Python-level error class that define .Wrap()
    e = EError("try", "fail")
    w = EErrorWrap("topic", e)
    e1 = Unwrap1(w)
    assert e1 is e
    assert Unwrap1(e1) is None

    # same, but wrapped is !error
    e = RuntimeError("zzz")
    w = EErrorWrap("qqq", e)
    e1 = Unwrap1(w)
    assert e1 is e
    assert Unwrap1(e1) is None


# verify Is for simple linear cases.
def test_is():
    E = errors.New
    Ec = error_mkchain

    assert errors.Is(None,    None)     == True
    assert errors.Is(E("a"),  None)     == False
    assert errors.Is(None,    E("b"))   == False

    # don't accept !error err
    assert errors.Is(BaseException(), None) == False
    with raises(TypeError): errors.Is(1, None)
    with raises(TypeError): errors.Is(object(), None)


    ewrap = Ec(["hello", "world", "мир"])

    assert errors.Is(ewrap, E("мир"))   == True
    assert errors.Is(ewrap, E("май"))   == False

    assert errors.Is(ewrap, Ec(["world", "мир"]))   == True
    assert errors.Is(ewrap, Ec(["hello", "мир"]))   == False
    assert errors.Is(ewrap, Ec(["hello", "май"]))   == False
    assert errors.Is(ewrap, Ec(["world", "май"]))   == False

    assert errors.Is(ewrap, Ec(["hello", "world", "мир"]))  == True
    assert errors.Is(ewrap, Ec(["a",     "world", "мир"]))  == False
    assert errors.Is(ewrap, Ec(["hello", "b",     "мир"]))  == False
    assert errors.Is(ewrap, Ec(["hello", "world", "c"]))    == False

    assert errors.Is(ewrap, Ec(["x", "hello", "world", "мир"])) == False

    # test with XWrap that defines .Unwrap() but not .Error()
    ewrap = XWrap("qqq", Ec(["abc", "привет"]))
    assert errors.Is(ewrap, E("zzz"))               == False
    assert errors.Is(ewrap, E("привет"))            == True
    assert errors.Is(ewrap, Ec(["abc", "привет"]))  == True
    assert errors.Is(ewrap, ewrap)                  == True
    w2 = XWrap("qqq", Ec(["abc", "def"]))
    assert errors.Is(ewrap, w2)                     == False
    w2 = XWrap("qqq", Ec(["abc", "привет"]))
    assert errors.Is(ewrap, w2)                     == True


# ---- Unwrap/Is in the presence of both .Unwrap and .__cause__ ----


# U returns [] with e error chain built via e.Unwrap and e.__cause__ recursion.
def U(e):
    if e is None:
        return []
    return [e] + U(getattr(e,'Unwrap',lambda:None)()) + U(getattr(e,'__cause__',None))

# Uunwrap returns [] with e error chain built via errors.Unwrap recursion.
def Uunwrap(e):
    return [e] + list(_errors._pyUnwrapIter(e))

# verifyUnwrap verifies errors.UnwrapIter via comparing its result with direct
# recursion through .Unwrap and .__cause__ .
def verifyUnwrap(e, estrvok):
    assert [str(_) for _ in U(e)] == estrvok
    assert Uunwrap(e) == U(e)

# verify how errors.Unwrap and errors.Is handle unwrapping when .__cause__ is also !None.
def test_unwrap_with_cause():
    E  = errors.New
    Ec = error_mkchain
    V  = verifyUnwrap

    V(E("abc"), ["abc"])
    V(E("hello world"), ["hello world"])

    #   e1 w→ e2 w→ e3                  e1 w→ e2 w→ e3
    #   |                     ->        |            w
    #   v                               v            |
    #   X                               X ← ← ← ← ← ←
    e1 = Ec(["1", "2", "3"])
    x  = XExc("x")
    e1.__cause__ = x
    V(e1, ["1: 2: 3", "2: 3", "3", "x"])
    assert errors.Is(e1, Ec(["1", "2", "3"]))   == True
    assert errors.Is(e1, Ec(["2", "3"]))        == True
    assert errors.Is(e1, Ec(["2", "4"]))        == False
    assert errors.Is(e1, E("3"))                == True
    assert errors.Is(e1, XExc("x"))             == True
    assert errors.Is(e1, XExc("y"))             == False

    #   e11 w→ e12 w→ e13               e11 w→ e12 w→ e13
    #   |                               | ← ← ← ← ← ← ← w
    #   v                     ->        v↓
    #   e21 w→ e22                      e21 w→ e22
    e11 = Ec(["11", "12", "13"])
    e21 = Ec(["21", "22"])
    e11.__cause__ = e21
    V(e11, ["11: 12: 13", "12: 13", "13", "21: 22", "22"])
    assert errors.Is(e11, Ec(["11", "12", "13"]))   == True
    assert errors.Is(e11, Ec(["12", "13"]))         == True
    assert errors.Is(e11, Ec(["12", "14"]))         == False
    assert errors.Is(e11, E("13"))                  == True
    assert errors.Is(e11, Ec(["11", "12", "13", "21", "22"]))   == False
    assert errors.Is(e11, Ec(["11", "12", "13", "21"]))         == False
    assert errors.Is(e11, Ec(["21", "22"]))         == True
    assert errors.Is(e11, E("22"))                  == True
    assert errors.Is(e11, Ec(["21", "22", "23"]))   == False
    assert errors.Is(e11, Ec(["21", "23"]))         == False

    #   e1 w→ e2 w→ e3
    #   |     |      w
    #   v     v      |
    #   X1← ← X2← ← ←
    e2 = Ec(["2", "3"])
    e1 = EErrorWrap("1", e2)
    x1 = XExc("x1")
    x2 = XExc("x2")
    e1.__cause__ = x1
    e2.__cause__ = x2
    V(e1, ["1: 2: 3", "2: 3", "3", "x2", "x1"])
    assert errors.Is(e1, EErrorWrap("1", Ec(["2", "3"])))   == True
    assert errors.Is(e1, EErrorWrap("1", Ec(["2", "4"])))   == False
    assert errors.Is(e1, EErrorWrap("0", Ec(["2", "3"])))   == False
    assert errors.Is(e1, Ec(["2", "3"]))                    == True
    assert errors.Is(e1, Ec(["2", "4"]))                    == False
    assert errors.Is(e1, XExc("x1"))                        == True
    assert errors.Is(e1, XExc("x2"))                        == True
    assert errors.Is(e1, XExc("x3"))                        == False

    #   e11 w→ e12 w→ e13
    #   |      |       w
    #   v      v .← ← ←'
    #   X1    e21 w→ e22
    #     `← ← ← ← ← ←'
    e13 = XExc("13")
    e12 = EErrorWrap("12", e13)
    e11 = XWrap("11", e12)
    x1  = XExc("x1")
    e21 = Ec(["21", "22"])
    e11.__cause__ = x1
    e12.__cause__ = e21
    V(e11, ["11: 12: 13", "12: 13", "13", "21: 22", "22", "x1"])
    assert errors.Is(e11, EErrorWrap("12", XExc("13")))     == True
    assert errors.Is(e11, EErrorWrap("12", XExc("14")))     == False
    assert errors.Is(e11, EErrorWrap("xx", XExc("13")))     == False
    assert errors.Is(e11, XExc("13"))                       == True
    assert errors.Is(e11, XExc("x1"))                       == True
    assert errors.Is(e11, XExc("y"))                        == False
    assert errors.Is(e11, Ec(["21", "22"]))                 == True
    assert errors.Is(e11, E("22"))                          == True
    assert errors.Is(e11, Ec(["21", "23"]))                 == False
    assert errors.Is(e11, E("23"))                          == False

    #   X1 w→ X2
    #   |     w
    #   v .← ←'
    #   e1 w→ e2 w→ e3
    x2 = XExc("x2")
    x1 = XWrap("x1", x2)
    e1 = Ec(["1", "2", "3"])
    x1.__cause__ = e1
    V(x1, ["x1: x2", "x2", "1: 2: 3", "2: 3", "3"])
    assert errors.Is(x1, XExc("x2"))                == True
    assert errors.Is(x1, XExc("x3"))                == False
    assert errors.Is(x1, XWrap("x1", XExc("x2")))   == True
    assert errors.Is(x1, XWrap("x1", XExc("x3")))   == False
    assert errors.Is(x1, XWrap("y1", XExc("x2")))   == False
    assert errors.Is(x1, Ec(["1", "2", "3"]))       == True
    assert errors.Is(x1, Ec(["2", "3"]))            == True
    assert errors.Is(x1, E("3"))                    == True
    assert errors.Is(x1, Ec(["2", "4"]))            == False

    #   X11 w→ X12
    #   |
    #   v
    #   X21 w→ X22
    x12 = XExc("x12")
    x11 = XWrap("x11", x12)
    x22 = XExc("x22")
    x21 = XWrap("x21", x22)
    x11.__cause__ = x21
    V(x11, ["x11: x12", "x12", "x21: x22", "x22"])
    assert errors.Is(x11, XExc("x12"))                  == True
    assert errors.Is(x11, XExc("x13"))                  == False
    assert errors.Is(x11, XWrap("x11", XExc("x12")))    == True
    assert errors.Is(x11, XWrap("y11", XExc("x12")))    == False
    assert errors.Is(x11, XExc("x22"))                  == True
    assert errors.Is(x11, XExc("x23"))                  == False
    assert errors.Is(x11, XWrap("x21", XExc("x22")))    == True
    assert errors.Is(x11, XWrap("y21", XExc("x22")))    == False
    assert errors.Is(x11, XWrap("x11", XWrap("x21", XExc("x22"))))  == False
