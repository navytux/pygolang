# -*- coding: utf-8 -*-
# Copyright (C) 2022-2025  Nexedi SA and Contributors.
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
from golang.golang_str_test import xbytes, unicode
from pytest import raises, fixture
import io, struct
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


# verify that loading *UNICODE opcodes loads them as unicode/ustr.
# this is standard behaviour but we verify it since we will patch pickle's strings processing.
# also verify save lightly for symmetry.
def test_strings_pickle_loadsave_UNICODE(pickle):
    # NOTE builtin pickle behaviour is to save unicode via 'surrogatepass' error handler
    #      this means that b'мир\xff' -> ustr/unicode -> save will emit *UNICODE with
    #      b'мир\xed\xb3\xbf' instead of b'мир\xff' as data.
    p_uni   = b'V\\u043c\\u0438\\u0440\\udcff\n.'                       # UNICODE 'мир\uDCFF'
    p_binu  = b'X\x09\x00\x00\x00\xd0\xbc\xd0\xb8\xd1\x80\xed\xb3\xbf.' # BINUNICODE  NOTE ...edb3bf not ...ff
    p_sbinu = b'\x8c\x09\xd0\xbc\xd0\xb8\xd1\x80\xed\xb3\xbf.'          # SHORT_BINUNICODE
    p_binu8 = b'\x8d\x09\x00\x00\x00\x00\x00\x00\x00\xd0\xbc\xd0\xb8\xd1\x80\xed\xb3\xbf.' # BINUNICODE8

    u_obj = u'мир\uDCFF'; assert type(u_obj) is unicode

    # load: check invokes f on all test pickles that pickle should support
    def check(f):
        f(p_uni)
        f(p_binu)
        if HIGHEST_PROTOCOL(pickle) >= 4:
            f(p_sbinu)
            f(p_binu8)

    def _(p):
        obj = xloads(pickle, p)
        assert type(obj) is unicode
        assert obj == u_obj
    check(_)

    # save
    def dumps(proto):
        return xdumps(pickle, u_obj, proto)
    assert dumps(0) == p_uni
    assert dumps(1) == p_binu
    assert dumps(2) == p_binu
    if HIGHEST_PROTOCOL(pickle) >= 3:
        assert dumps(3) == p_binu
    if HIGHEST_PROTOCOL(pickle) >= 4:
        assert dumps(4) == p_sbinu


# verify that bstr/ustr can be pickled/unpickled correctly.
def test_strings_pickle_bstr_ustr(pickle):
    bs = b(xbytes('мир')+b'\xff')
    us = u(xbytes('май')+b'\xff')

    def diss(p): return xdiss(pickle2tools(pickle), p)
    def dis(p): print(diss(p))

    # assert_pickle verifies that pickling obj results in dumps_ok
    # and that unpickling results back in obj.
    assert HIGHEST_PROTOCOL(pickle) <= 5
    def assert_pickle(obj, proto, dumps_ok):
        if proto > HIGHEST_PROTOCOL(pickle):
            with raises(ValueError):
                xdumps(pickle, obj, proto)
            return
        p = xdumps(pickle, obj, proto)
        assert p == dumps_ok, diss(p)
        #dis(p)
        obj2 = xloads(pickle, p)
        assert type(obj2) is type(obj)
        assert obj2 == obj

    _ = assert_pickle

    _(bs, 0,
             b"cgolang\n_butf8b\n(V\\u043c\\u0438\\u0440\\udcff\ntR.")      # _butf8b(UNICODE)

    _(us, 0,
             b'cgolang\nustr\n(V\\u043c\\u0430\\u0439\\udcff\ntR.')         # ustr(UNICODE)

    _(bs, 1,
             b'cgolang\n_butf8b\n(X\x09\x00\x00\x00'                        # _butf8b(BINUNICODE)
                        b'\xd0\xbc\xd0\xb8\xd1\x80\xed\xb3\xbftR.')

    # NOTE BINUNICODE ...edb3bf not ...ff  (see test_strings_pickle_loadsave_UNICODE for details)
    _(us, 1,
             b'cgolang\nustr\n(X\x09\x00\x00\x00'                           # ustr(BINUNICODE)
                        b'\xd0\xbc\xd0\xb0\xd0\xb9\xed\xb3\xbftR.')

    _(bs, 2,
             b'cgolang\n_butf8b\nX\x09\x00\x00\x00'                         # _butf8b(BINUNICODE)
                        b'\xd0\xbc\xd0\xb8\xd1\x80\xed\xb3\xbf\x85R.')

    _(us, 2,
             b'cgolang\nustr\nX\x09\x00\x00\x00'                            # ustr(BINUNICODE)
                        b'\xd0\xbc\xd0\xb0\xd0\xb9\xed\xb3\xbf\x85\x81.')

    _(bs, 3,
             b'cgolang\nbstr\nC\x07\xd0\xbc\xd0\xb8\xd1\x80\xff\x85\x81.')  # bstr(SHORT_BINBYTES)

    _(us, 3,
             b'cgolang\nustr\nX\x09\x00\x00\x00'                            # ustr(BINUNICODE)
                        b'\xd0\xbc\xd0\xb0\xd0\xb9\xed\xb3\xbf\x85\x81.')

    for p in (4,5):
        _(bs, p,
             b'\x8c\x06golang\x8c\x04bstr\x93C\x07'                         # bstr(SHORT_BINBYTES)
                        b'\xd0\xbc\xd0\xb8\xd1\x80\xff\x85\x81.')
        _(us, p,
             b'\x8c\x06golang\x8c\x04ustr\x93\x8c\x09'                      # ustr(SHORT_BINUNICODE)
                        b'\xd0\xbc\xd0\xb0\xd0\xb9\xed\xb3\xbf\x85\x81.')


# ---- disassembly ----

# xdiss returns disassembly of a pickle as string.
def xdiss(pickletools, p): # -> str
    out = six.StringIO()
    pickletools.dis(p, out)
    return out.getvalue()


# ---- loads and normalized dumps ----

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

    # remove not interesting parts: PROTO / FRAME header and unused PUTs
    if proto >= 2:
        assert p1.startswith(PROTO(proto))
    return pickle_normalize(pickle2tools(pickle), p1)

def _xpickle_attr(pickle, name):
    # on py3 pickle.py tries to import from C _pickle to optimize by default
    # -> verify py version if we are asked to test pickle.py
    if six.PY3 and (pickle is stdPickle):
        assert getattr(pickle, name) is getattr(cPickle, name)
        name = '_'+name
    return getattr(pickle, name)

# pickle_normalize returns normalized version of pickle p.
#
# - PROTO and FRAME opcodes are removed from header,
# - unused PUT, BINPUT and MEMOIZE opcodes - those without corresponding GET are removed,
# - *PUT indices start from 0 (this unifies cPickle with pickle).
def pickle_normalize(pickletools, p):
    def iter_pickle(p): # -> i(op, arg, pdata)
        op_prev  = None
        arg_prev = None
        pos_prev = None
        for op, arg, pos in pickletools.genops(p):
            if op_prev is not None:
                pdata_prev = p[pos_prev:pos]
                yield (op_prev, arg_prev, pdata_prev)
            op_prev  = op
            arg_prev = arg
            pos_prev = pos
        if op_prev is not None:
            yield (op_prev, arg_prev, p[pos_prev:])

    memo_oldnew = {} # idx used in original pop/get -> new index | None if not get
    idx = 0
    for op, arg, pdata in iter_pickle(p):
        if 'PUT' in op.name:
            memo_oldnew.setdefault(arg, None)
        elif 'MEMOIZE' in op.name:
            memo_oldnew.setdefault(len(memo_oldnew), None)
        elif 'GET' in op.name:
            if memo_oldnew.get(arg) is None:
                memo_oldnew[arg] = idx
                idx += 1

    pout = b''
    memo_old = set() # idx used in original pop
    for op, arg, pdata in iter_pickle(p):
        if op.name in ('PROTO', 'FRAME'):
            continue
        if 'PUT' in op.name:
            memo_old.add(arg)
            newidx = memo_oldnew.get(arg)
            if newidx is None:
                continue
            pdata = globals()[op.name](newidx)
        if 'MEMOIZE' in op.name:
            idx = len(memo_old)
            memo_old.add(idx)
            newidx = memo_oldnew.get(idx)
            if newidx is None:
                continue
        if 'GET' in op.name:
            newidx = memo_oldnew[arg]
            assert newidx is not None
            pdata = globals()[op.name](newidx)
        pout += pdata
    return pout

P = struct.pack
def PROTO(version):     return b'\x80'  + P('<B', version)
def FRAME(size):        return b'\x95'  + P('<Q', size)
def GET(idx):           return b'g%d\n' % (idx,)
def PUT(idx):           return b'p%d\n' % (idx,)
def BINPUT(idx):        return b'q'     + P('<B', idx)
def BINGET(idx):        return b'h'     + P('<B', idx)
def LONG_BINPUT(idx):   return b'r'     + P('<I', idx)
def LONG_BINGET(idx):   return b'j'     + P('<I', idx)
MEMOIZE =                      b'\x94'

def test_pickle_normalize(pickletools):
    def diss(p):
        return xdiss(pickletools, p)

    proto = 0
    for op in pickletools.opcodes:
        proto = max(proto, op.proto)
    assert proto >= 2

    def _(p, p_normok):
        p_norm = pickle_normalize(pickletools, p)
        assert p_norm == p_normok, diss(p_norm)

    _(b'.', b'.')
    _(b'I1\n.', b'I1\n.')
    _(PROTO(2)+b'I1\n.', b'I1\n.')

    putgetv = [(PUT,GET), (BINPUT, BINGET)]
    if proto >= 4:
        putgetv.append((LONG_BINPUT, LONG_BINGET))
    for (put,get) in putgetv:
        _(b'(I1\n'+put(1) + b'I2\n'+put(2) +b't'+put(3)+b'0'+get(3)+put(4)+b'.',
          b'(I1\nI2\nt'+put(0)+b'0'+get(0)+b'.')

    if proto >= 4:
        _(FRAME(4)+b'I1\n.', b'I1\n.')
        _(b'I1\n'+MEMOIZE+b'I2\n'+MEMOIZE+GET(0)+b'.',
          b'I1\n'+MEMOIZE+b'I2\n'+GET(0)+b'.')


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
