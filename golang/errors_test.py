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
from golang import errors
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
