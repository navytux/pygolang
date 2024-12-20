# -*- coding: utf-8 -*-
# Copyright (C) 2022-2024  Nexedi SA and Contributors.
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

from golang import b, u, bstr, ustr
from pytest import fixture
import io
import six

# run all tests on all py/c pickle modules we aim to support
import pickle as stdPickle
if six.PY2:
    import cPickle
else:
    import _pickle as cPickle
from zodbpickle import slowpickle as zslowPickle
from zodbpickle import fastpickle as zfastPickle
from zodbpickle import pickle  as zpickle
from zodbpickle import _pickle as _zpickle
import pickletools as stdpickletools
if six.PY2:
    from zodbpickle import pickletools_2 as zpickletools
else:
    from zodbpickle import pickletools_3 as zpickletools


# pickle is pytest fixture that yields all variants of pickle module.
@fixture(scope="function", params=[stdPickle, cPickle,
                                   zslowPickle, zfastPickle, zpickle, _zpickle])
def pickle(request):
    yield request.param

# pickletools is pytest fixture that yields all variants of pickletools module.
@fixture(scope="function", params=[stdpickletools, zpickletools])
def pickletools(request):
    yield request.param

# pickle2tools returns pickletools module that corresponds to module pickle.
def pickle2tools(pickle):
    if pickle in (stdPickle, cPickle):
        return stdpickletools
    else:
        return zpickletools


# verify that bstr/ustr can be pickled/unpickled correctly.
def test_strings_pickle(pickle):
    bs = b("мир")
    us = u("май")

    def diss(p): return xdiss(pickle2tools(pickle), p)
    def dis(p): print(diss(p))

    for proto in range(0, HIGHEST_PROTOCOL(pickle)+1):
        p_bs = xdumps(pickle, bs, proto)
        #dis(p_bs)
        bs_ = xloads(pickle, p_bs)
        assert type(bs_) is bstr
        assert bs_ == bs

        p_us = xdumps(pickle, us, proto)
        #dis(p_us)
        us_ = xloads(pickle, p_us)
        assert type(us_) is ustr
        assert us_ == us


# ---- disassembly ----

# xdiss returns disassembly of a pickle as string.
def xdiss(pickletools, p): # -> str
    out = six.StringIO()
    pickletools.dis(p, out)
    return out.getvalue()


# ---- loads and dumps ----

# xloads loads pickle p via pickle.loads
# it also verifies that .load and Unpickler.load give the same result.
def xloads(pickle, p, **kw):
    obj1 = _xpickle_attr(pickle, 'loads')(p, **kw)
    obj2 = _xpickle_attr(pickle, 'load') (io.BytesIO(p), **kw)
    obj3 = _xpickle_attr(pickle, 'Unpickler')(io.BytesIO(p), **kw).load()
    assert type(obj2) is type(obj1)
    assert type(obj3) is type(obj1)
    assert obj1 == obj2 == obj3
    return obj1

# xdumps dumps obj via pickle.dumps
# it also verifies that .dump and Pickler.dump give the same.
def xdumps(pickle, obj, proto, **kw):
    p1 = _xpickle_attr(pickle, 'dumps')(obj, proto, **kw)
    f2 = io.BytesIO();  _xpickle_attr(pickle, 'dump')(obj, f2, proto, **kw)
    p2 = f2.getvalue()
    f3 = io.BytesIO();  _xpickle_attr(pickle, 'Pickler')(f3, proto, **kw).dump(obj)
    p3 = f3.getvalue()
    assert type(p1) is bytes
    assert type(p2) is bytes
    assert type(p3) is bytes
    assert p1 == p2 == p3

    return p1

def _xpickle_attr(pickle, name):
    # on py3 pickle.py tries to import from C _pickle to optimize by default
    # -> verify py version if we are asked to test pickle.py
    if six.PY3 and (pickle is stdPickle):
        assert getattr(pickle, name) is getattr(cPickle, name)
        name = '_'+name
    return getattr(pickle, name)


# ---- misc ----

# HIGHEST_PROTOCOL returns highest protocol supported by pickle.
def HIGHEST_PROTOCOL(pickle):
    if   six.PY3  and  pickle is cPickle:
        pmax = stdPickle.HIGHEST_PROTOCOL  # py3: _pickle has no .HIGHEST_PROTOCOL
    elif six.PY3  and  pickle is _zpickle:
        pmax = zpickle.HIGHEST_PROTOCOL    # ----//---- for _zpickle
    else:
        pmax = pickle.HIGHEST_PROTOCOL
    assert pmax >= 2
    return pmax
