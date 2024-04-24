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
from golang.golang_str_test import xbytes, x32, unicode
from golang._golang import _test_inside_counted, _test_cfunc_is_callee_cleanup
from gpython.gpython_test import is_gpython
from pytest import raises, fixture, mark
import sys, io, struct
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

# @gpystr_only is marker to run a test only under gpython -X gpython.strings=bstr+ustr
is_gpystr = type(u'') is ustr
gpystr_only = mark.skipif(not is_gpystr, reason="gpystr-only test")


# ---- pickling/unpickling under gpystr ----

# test pickles with *STRING
STRING_bytes = xbytes('мир')+b'\xff'    # binary data in all test *STRING pickles
p_str   = b"S'\\xd0\\xbc\\xd0\\xb8\\xd1\\x80\\xff'\n."      # STRING 'мир\xff'
p_utf8  = b"S'"+xbytes('мир')+b"\\xff'\n."                  # STRING 'мир\xff'
p_sbins = b'U\x07\xd0\xbc\xd0\xb8\xd1\x80\xff.'             # SHORT_BINSTRING 'мир\xff'
p_bins  = b'T\x07\x00\x00\x00\xd0\xbc\xd0\xb8\xd1\x80\xff.' # BINSTRING 'мир\xff'

# checkSTRING invokes f on all test *STRING pickles.
def checkSTRING(f):
    f(p_str)
    f(p_utf8)
    f(p_sbins)
    f(p_bins)

# verify that loading *STRING opcodes loads them as bstr on gpython by default.
@gpystr_only
def test_strings_pickle_load_STRING(pickle):
    check = checkSTRING

    # default -> bstr  on both py2 and py3
    def _(p):
        obj = xloads(pickle, p)
        assert type(obj) is bstr
        assert obj == STRING_bytes
    check(_)

    # also test bstr inside tuple (for symmetry with save)
    def _(p):
        p_ = b'(' + p[:-1] + b't.'
        tobj = xloads(pickle, p_)
        assert type(tobj) is tuple
        assert len(tobj) == 1
        obj = tobj[0]
        assert type(obj) is bstr
        assert obj == STRING_bytes
    check(_)

    # also test bstr used as persistent reference directly and as part of tuple (symmetry with save)
    def _(p):
        p_ = p[:-1] + b'Q.'
        pobj = ploads(pickle, p_)
        assert type(pobj) is tPersistent
        assert type(pobj._p_oid) is bstr
        assert pobj._p_oid == STRING_bytes
    check(_)
    def _(p):
        p_ = b'(' + p[:-1] + b'tQ.'
        pobj = ploads(pickle, p_)
        assert type(pobj) is tPersistent
        assert type(pobj._p_oid) is tuple
        assert len(pobj._p_oid) == 1
        obj = pobj._p_oid[0]
        assert type(obj) is bstr
        assert obj == STRING_bytes
    check(_)

# verify that saving bstr results in *STRING opcodes on gpython.
@gpystr_only
def test_strings_pickle_save_STRING(pickle):
    s = s0 = b(STRING_bytes)
    assert type(s) is bstr

    def dumps(proto):
        return xdumps(pickle, s, proto)

    assert dumps(0) == p_utf8
    for proto in range(1, HIGHEST_PROTOCOL(pickle)+1):
        assert dumps(proto) == p_sbins

    # BINSTRING
    s += b'\x55'*0x100
    p_bins_ = p_bins[:2] + b'\x01' + p_bins[3:-1] + b'\x55'*0x100 + b'.'
    for proto in range(1, HIGHEST_PROTOCOL(pickle)+1):
        assert dumps(proto) == p_bins_

    # also test bstr inside tuple to verify that what we patched is actually
    # _pickle.save that is invoked from inside other save_X functions.
    s = (s0,)
    p_tuple_utf8  = b'(' + p_utf8[:-1]  + b't.'
    p_tuple_sbins = b'(' + p_sbins[:-1] + b't.'
    assert dumps(0) == p_tuple_utf8
    assert dumps(1) == p_tuple_sbins
    # don't test proto ≥ 2 because they start to use TUPLE1 instead of TUPLE

    # also test bstr used as persistent reference to verify pers_save codepath
    obj = tPersistent(s0)
    def dumps(proto):
        return pdumps(pickle, obj, proto)
    assert dumps(0) == b'P' + STRING_bytes + '\n.'
    for proto in range(1, HIGHEST_PROTOCOL(pickle)+1):
        assert dumps(proto) == p_sbins[:-1] + b'Q.'

    # ... and peristent reference being tuple to verifiy pers_save
    # stringification in proto=0 and recursion to save in proto≥1.
    obj = tPersistent((s0,))
    try:
        assert dumps(0) == b'P(' + p_utf8[1:-2] + ',)\n.'
    except pickle.PicklingError as e:
        # on py2 cpickle insists that with proto=0 pid must be string
        if six.PY2:
            assert e.args == ('persistent id must be string',)
        else:
            raise
    assert dumps(1) == p_tuple_sbins[:-1] + b'Q.'
    # no proto ≥ 2 because they start to use TUPLE1 instead of TUPLE

    # proto 0 with \n in persid -> rejected
    obj = tPersistent(b('a\nb'))
    if six.PY3: # TODO also consider patching save_pers codepath on py2
        with raises(pickle.PicklingError, match=r'persistent ID contains \\n') as e:
            dumps(0)
    for proto in range(1, HIGHEST_PROTOCOL(pickle)+1):
        assert dumps(proto) == b'U\x03a\nbQ.'


# verify that unpickling handles encoding=bstr|* .
# TODO also handle encoding='bstr' under plain py
@mark.skipif(not six.PY3, reason="pickle supports encoding=... only on py3")
@gpystr_only
def test_strings_pickle_load_encoding(pickle):
    check = checkSTRING

    # encoding='bstr'  -> bstr
    def _(p):
        obj = xloads(pickle, p, encoding='bstr')
        assert type(obj) is bstr
        assert obj == STRING_bytes
    check(_)

    # encoding='bytes' -> bytes
    def _(p):
        obj = xloads(pickle, p, encoding='bytes')
        assert type(obj) is bytes
        assert obj == STRING_bytes
    check(_)

    # encoding='utf-8' -> UnicodeDecodeError
    def _(p):
        with raises(UnicodeDecodeError):
            xloads(pickle, p, encoding='utf-8')
    check(_)

    # encoding='utf-8', errors=... -> unicode
    def _(p):
        obj = xloads(pickle, p, encoding='utf-8', errors='backslashreplace')
        assert type(obj) is unicode
        assert obj == u'мир\\xff'
    check(_)



# verify that loading *UNICODE opcodes loads them as unicode/ustr.
# this is standard behaviour but we verify it since we patch pickle's strings processing.
# also verify save lightly for symmetry.
# NOTE not @gpystr_only
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


# ---- pickling/unpickling generally without gpystr ----

# verify that bstr/ustr can be pickled/unpickled correctly on !gpystr.
# gpystr should also load ok what was pickled on !gpystr.
# for uniformity gpystr is also verified to save/load objects correctly.
# However the main gpystr tests are load/save tests for *STRING and *UNICODE above.
def test_strings_pickle_bstr_ustr(pickle):
    bs = b(xbytes('мир')+b'\xff')
    us = u(xbytes('май')+b'\xff')

    def diss(p): return xdiss(pickle2tools(pickle), p)
    def dis(p): print(diss(p))

    # assert_pickle verifies that pickling obj results in
    #
    #   - dumps_ok_gpystr  (when run under gpython with gpython.string=bstr+ustr),  or
    #   - dumps_ok_stdstr  (when run under plain python or gpython with gpython.strings=pystd)
    #
    # and that unpickling results back in obj.
    #
    # gpystr should also unpickle !gpystr pickle correctly.
    assert HIGHEST_PROTOCOL(pickle) <= 5
    def assert_pickle(obj, proto, dumps_ok_gpystr, dumps_ok_stdstr):
        if proto > HIGHEST_PROTOCOL(pickle):
            with raises(ValueError):
                xdumps(pickle, obj, proto)
            return
        p = xdumps(pickle, obj, proto)
        if not is_gpystr:
            assert p == dumps_ok_stdstr, diss(p)
            dumps_okv = [dumps_ok_stdstr]
        else:
            assert p == dumps_ok_gpystr, diss(p)
            dumps_okv = [dumps_ok_gpystr, dumps_ok_stdstr]
        for p in dumps_okv:
            #dis(p)
            obj2 = xloads(pickle, p)
            assert type(obj2) is type(obj)
            assert obj2 == obj

    _ = assert_pickle

    _(bs, 0, xbytes("S'мир\\xff'\n."),                                      # STRING
             b"cgolang\nbstr\n(V\\u043c\\u0438\\u0440\\udcff\ntR.")         # bstr(UNICODE)

    _(us, 0, b'V\\u043c\\u0430\\u0439\\udcff\n.',                           # UNICODE
             b'cgolang\nustr\n(V\\u043c\\u0430\\u0439\\udcff\ntR.')         # ustr(UNICODE)

    _(bs, 1, b'U\x07\xd0\xbc\xd0\xb8\xd1\x80\xff.',                         # SHORT_BINSTRING
             b'cgolang\nbstr\n(X\x09\x00\x00\x00'                           # bstr(BINUNICODE)
                        b'\xd0\xbc\xd0\xb8\xd1\x80\xed\xb3\xbftR.')

    # NOTE BINUNICODE ...edb3bf not ...ff  (see test_strings_pickle_loadsave_UNICODE for details)
    _(us, 1, b'X\x09\x00\x00\x00\xd0\xbc\xd0\xb0\xd0\xb9\xed\xb3\xbf.',     # BINUNICODE
             b'cgolang\nustr\n(X\x09\x00\x00\x00'                           # bstr(BINUNICODE)
                        b'\xd0\xbc\xd0\xb0\xd0\xb9\xed\xb3\xbftR.')

    _(bs, 2, b'U\x07\xd0\xbc\xd0\xb8\xd1\x80\xff.',                         # SHORT_BINSTRING
             b'cgolang\nbstr\nX\x09\x00\x00\x00'                            # bstr(BINUNICODE)
                        b'\xd0\xbc\xd0\xb8\xd1\x80\xed\xb3\xbf\x85\x81.')

    _(us, 2, b'X\x09\x00\x00\x00\xd0\xbc\xd0\xb0\xd0\xb9\xed\xb3\xbf.',     # BINUNICODE
             b'cgolang\nustr\nX\x09\x00\x00\x00'                            # ustr(BINUNICODE)
                        b'\xd0\xbc\xd0\xb0\xd0\xb9\xed\xb3\xbf\x85\x81.')

    _(bs, 3, b'U\x07\xd0\xbc\xd0\xb8\xd1\x80\xff.',                         # SHORT_BINSTRING
             b'cgolang\nbstr\nC\x07\xd0\xbc\xd0\xb8\xd1\x80\xff\x85\x81.')  # bstr(SHORT_BINBYTES)

    _(us, 3, b'X\x09\x00\x00\x00\xd0\xbc\xd0\xb0\xd0\xb9\xed\xb3\xbf.',     # BINUNICODE
             b'cgolang\nustr\nX\x09\x00\x00\x00'                            # ustr(BINUNICODE)
                        b'\xd0\xbc\xd0\xb0\xd0\xb9\xed\xb3\xbf\x85\x81.')

    for p in (4,5):
        _(bs, p,
             b'U\x07\xd0\xbc\xd0\xb8\xd1\x80\xff.',                         # SHORT_BINSTRING
             b'\x8c\x06golang\x8c\x04bstr\x93C\x07'                         # bstr(SHORT_BINBYTES)
                        b'\xd0\xbc\xd0\xb8\xd1\x80\xff\x85\x81.')
        _(us, p,
             b'\x8c\x09\xd0\xbc\xd0\xb0\xd0\xb9\xed\xb3\xbf.',              # SHORT_BINUNICODE
             b'\x8c\x06golang\x8c\x04ustr\x93\x8c\x09'                      # ustr(SHORT_BINUNICODE)
                        b'\xd0\xbc\xd0\xb0\xd0\xb9\xed\xb3\xbf\x85\x81.')


# ---- disassembly ----

# xdiss returns disassembly of a pickle as string.
def xdiss(pickletools, p): # -> str
    out = six.StringIO()
    pickletools.dis(p, out)
    return out.getvalue()

# verify that disassembling *STRING and related opcodes works with treating strings as UTF8b.
@gpystr_only
def test_strings_pickle_dis_STRING(pickletools):
    brepr = repr(b(STRING_bytes))

    assert xdiss(pickletools, p_str) == """\
    0: S    STRING     %s
   32: .    STOP
highest protocol among opcodes = 0
""" % brepr

    assert xdiss(pickletools, p_utf8) == """\
    0: S    STRING     %s
   14: .    STOP
highest protocol among opcodes = 0
""" % brepr

    assert xdiss(pickletools, p_sbins) == """\
    0: U    SHORT_BINSTRING %s
    9: .    STOP
highest protocol among opcodes = 1
""" % brepr

    assert xdiss(pickletools, p_bins) == """\
    0: T    BINSTRING  %s
   12: .    STOP
highest protocol among opcodes = 1
""" % brepr

    assert xdiss(pickletools, b'P' + STRING_bytes + b'\n.') == """\
    0: P    PERSID     %s
    9: .    STOP
highest protocol among opcodes = 0
""" % brepr


# ---- loads and normalized dumps ----

# xloads loads pickle p via pickle.loads
# it also verifies that .load and Unpickler.load give the same result.
#
# see also: ploads.
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
# the pickle is returned in normalized form - see pickle_normalize for details.
#
# see also: pdumps.
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

# ploads loads pickle p via pickle.Unpickler with handling persistent references.
#
# see also: xloads.
def ploads(pickle, p, **kw):
    Unpickler = _xpickle_attr(pickle, 'Unpickler')

    u1 = Unpickler(io.BytesIO(p), **kw)
    u1.persistent_load = lambda pid: tPersistent(pid)
    obj1 = u1.load()

    # same with .persistent_load defined as class method
    try:
        class Unpickler2(Unpickler):
            def persistent_load(self, pid): return tPersistent(pid)
    except TypeError:
        if six.PY2:
            # on py2 cPickle.Unpickler is not subclassable at all
            obj2 = obj1
        else:
            raise
    else:
        u2 = Unpickler2(io.BytesIO(p), **kw)
        obj2 = u2.load()

    assert obj1 == obj2
    return obj1

# pdumps dumps obj via pickle.Pickler with handling persistent references.
# the pickle is returned in normalized form - see pickle_normalize for details.
#
# see also: xdumps.
def pdumps(pickle, obj, proto, **kw):
    Pickler = _xpickle_attr(pickle, 'Pickler')

    f1 = io.BytesIO()
    p1 = Pickler(f1, proto, **kw)
    def _(obj):
        if isinstance(obj, tPersistent):
            return obj._p_oid
        return None
    p1.persistent_id = _
    p1.dump(obj)
    pobj1 = f1.getvalue()

    # same with .persistent_id defined as class method
    try:
        class Pickler2(Pickler):
            def persistent_id(self, obj):
                if isinstance(obj, tPersistent):
                    return obj._p_oid
                return None
    except TypeError:
        if six.PY2:
            # on py2 cPickle.Pickler is not subclassable at all
            pobj2 = pobj1
        else:
            raise
    else:
        f2 = io.BytesIO()
        p2 = Pickler2(f2, proto, **kw)
        p2.dump(obj)
        pobj2 = f2.getvalue()

    assert pobj1 == pobj2

    if proto >= 2:
        assert pobj1.startswith(PROTO(proto))
    return pickle_normalize(pickle2tools(pickle), pobj1)

# tPersistent is test class to verify handling of persistent references.
class tPersistent(object):
    def __init__(t, pid):
        t._p_oid = pid
    def __eq__(t, rhs): return (type(rhs) is type(t))  and  (rhs._p_oid == t._p_oid)
    def __ne__(t, rhs): return not (t.__eq__(rhs))

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


# ---- internals of patching ----

# being able to cPickle bstr as STRING depends on proper working of inside_counted function.
# Verify it with dedicated unit test.
def test_inside_counted(capsys):
    outok = _test_inside_counted()
    _ = capsys.readouterr()
    if _.err:
        print(_.err, file=sys.stderr)
    assert _.out == outok

def test_cfunc_is_callee_cleanup():
    _test_cfunc_is_callee_cleanup()

# verify that what we patched - e.g. PyUnicode_Decode - stay unaffected when
# called outside of bstr/ustr context.
# NOTE this test complements test_strings_patched_transparently in golang_str_test.py
def test_pickle_strings_patched_transparently():
    # PyUnicode_Decode stays working and unaffected
    b_  = xbytes("abc")
    _ = b_.decode();         assert type(_) is unicode;  assert _ == u"abc"
    _ = b_.decode("utf8");   assert type(_) is unicode;  assert _ == u"abc"
    _ = b_.decode("ascii");  assert type(_) is unicode;  assert _ == u"abc"

    b_  = xbytes("мир")
    _ = b_.decode("utf8");   assert type(_) is unicode;  assert _ == u"мир"
    with raises(UnicodeDecodeError):
        b_.decode("ascii")


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
