# -*- coding: utf-8 -*-
# cython: language_level=2
# Copyright (C) 2019  Nexedi SA and Contributors.
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
"""Package context mirrors Go package context.

See the following links about Go contexts:

    https://blog.golang.org/context
    https://golang.org/pkg/context
"""

from __future__ import print_function, absolute_import

from golang import go as pygo, select as pyselect, default as pydefault, nilchan as pynilchan
from golang import _sync as _pysync # avoid cycle: context -> sync -> context
from golang import time as pytime

from golang cimport pychan
from golang cimport time
from cython cimport final


# Context is the interface that every context must implement.
#
# A context carries deadline, cancellation signal and immutable context-local
# key -> value dict.
cdef class PyContext:
    # deadline() returns context deadline or None, if there is no deadline.
    def deadline(PyContext ctx):  # -> time | None
        raise NotImplementedError()

    # done returns channel that is closed when the context is canceled.
    def done(PyContext ctx):  # -> pychan(dtype='C.structZ')
        raise NotImplementedError()

    # err returns None if done is not yet closed, or error that explains why context was canceled.
    def err(PyContext ctx):   # -> error
        raise NotImplementedError()

    # value returns value associated with key, or None, if context has no key.
    def value(PyContext ctx, object key):  # -> value | None
        raise NotImplementedError()


# background returns empty context that is never canceled.
def pybackground(): # -> Context
    return  _pybackground

# canceled is the error returned by Context.err when context is canceled.
pycanceled = RuntimeError("context canceled")

# deadlineExceeded is the error returned by Context.err when time goes past context's deadline.
pydeadlineExceeded = RuntimeError("deadline exceeded")


# with_cancel creates new context that can be canceled on its own.
#
# Returned context inherits from parent and in particular is canceled when
# parent is done.
#
# The caller should explicitly call cancel to release context resources as soon
# the context is no longer needed.
def pywith_cancel(parent): # -> ctx, cancel
    ctx = _CancelCtx(parent)
    return ctx, lambda: ctx._cancel(pycanceled)

# with_value creates new context with key=value.
#
# Returned context inherits from parent and in particular has all other
# (key, value) pairs provided by parent.
def pywith_value(parent, object key, object value): # -> ctx
    return _ValueCtx({key: value}, parent)

# with_deadline creates new context with deadline.
#
# The deadline of created context is the earliest of provided deadline or
# deadline of parent. Created context will be canceled when time goes past
# context deadline or cancel called, whichever happens first.
#
# The caller should explicitly call cancel to release context resources as soon
# the context is no longer needed.
def pywith_deadline(parent, double deadline): # -> ctx, cancel
    # parent's deadline is before deadline -> just use parent
    pdead = parent.deadline()
    if pdead is not None and pdead <= deadline:
        return pywith_cancel(parent)

    # timeout <= 0   -> already canceled
    timeout = deadline - time.now()
    if timeout <= 0:
        ctx, cancel = pywith_cancel(parent)
        cancel()
        return ctx, cancel

    ctx = _TimeoutCtx(timeout, deadline, parent)
    return ctx, lambda: ctx._cancel(pycanceled)

# with_timeout creates new context with timeout.
#
# it is shorthand for with_deadline(parent, now+timeout).
def pywith_timeout(parent, double timeout): # -> ctx, cancel
    return pywith_deadline(parent, time.now() + timeout)

# merge merges 2 contexts into 1.
#
# The result context:
#
#   - is done when parent1 or parent2 is done, or cancel called, whichever happens first,
#   - has deadline = min(parent1.Deadline, parent2.Deadline),
#   - has associated values merged from parent1 and parent2, with parent1 taking precedence.
#
# Canceling this context releases resources associated with it, so code should
# call cancel as soon as the operations running in this Context complete.
#
# Note: on Go side merge is not part of stdlib context and is provided by
# https://godoc.org/lab.nexedi.com/kirr/go123/xcontext#hdr-Merging_contexts
def pymerge(parent1, parent2):  # -> ctx, cancel
    ctx = _CancelCtx(parent1, parent2)
    return ctx, lambda: ctx._cancel(pycanceled)

# --------

# _PyBackground implements root context that is never canceled.
@final
cdef class _PyBackground:
    def done(bg):
        return _nilchanZ

    def err(bg):
        return None

    def value(bg, key):
        return None

    def deadline(bg):
        return None

_pybackground = _PyBackground()
_nilchanZ   = pychan.nil('C.structZ')

# _BaseCtx is the common base for Contexts implemented in this package.
cdef class _BaseCtx:
    # parents of this context - either _BaseCtx* or generic Context.
    # does not change after setup.
    cdef tuple  _parentv

    cdef object _mu         # sync.PyMutex
    cdef set    _children   # children of this context - we propagate cancel there (all _BaseCtx)
    cdef object _err
    cdef object _done       # pychan | None

    def __init__(_BaseCtx ctx, done, *parentv):     # XXX done -> pychan?
        ctx._parentv    = parentv

        ctx._mu         = _pysync.PyMutex()
        ctx._children   = set()
        ctx._err        = None

        # pychan: if context can be canceled on its own
        # None:   if context can not be canceled on its own
        ctx._done       = done
        if done is None:
            assert len(parentv) == 1

        ctx._propagateCancel()

    def done(_BaseCtx ctx):
        if ctx._done is not None:
            return ctx._done
        return ctx._parentv[0].done()

    def err(_BaseCtx ctx):
        with ctx._mu:
            return ctx._err

    # value returns value for key from one of its parents.
    # this behaviour is inherited by all contexts except _ValueCtx who amends it.
    def value(_BaseCtx ctx, object key):
        for parent in ctx._parentv:
            v = parent.value(key)
            if v is not None:
                return v
        return None

    # deadline returns the earliest deadline of parents.
    # this behaviour is inherited by all contexts except _TimeoutCtx who overrides it.
    def deadline(_BaseCtx ctx):
        d = None
        for parent in ctx._parentv:
            pd = parent.deadline()
            if d is None or (pd is not None and pd < d):
                d = pd
        return d

    # _cancel cancels ctx and its children.
    def _cancel(_BaseCtx ctx, err):
        return ctx._cancelFrom(None, err)

    # _cancelFrom cancels ctx and its children.
    # if cancelFrom != None it indicates which ctx parent cancellation was the cause for ctx cancel.
    def _cancelFrom(_BaseCtx ctx, cancelFrom, err):
        with ctx._mu:
            if ctx._err is not None:
                return  # already canceled

            ctx._err = err
            children = ctx._children;   ctx._children = set()

        if ctx._done is not None:
            ctx._done.close()

        # no longer need to propagate cancel from parent after we are canceled
        for parent in ctx._parentv:
            if parent is cancelFrom:
                continue
            if isinstance(parent, _BaseCtx):
                _parent = <_BaseCtx>parent
                with _parent._mu:
                    if ctx in _parent._children:
                        _parent._children.remove(ctx)

        # propagate cancel to children
        for child in children:
            child._cancelFrom(ctx, err)


    # propagateCancel establishes setup so that whenever a parent is canceled,
    # ctx and its children are canceled too.
    def _propagateCancel(_BaseCtx ctx):
        pforeignv = [] # parents with !pynilchan .done() for foreign contexts
        for parent in ctx._parentv:
            # if parent can never be canceled (e.g. it is background) - we
            # don't need to propagate cancel from it.
            pdone = parent.done()
            if pdone == pynilchan:
                continue

            # parent is cancellable - glue to propagate cancel from it to us
            if isinstance(parent, _BaseCtx):
                _parent = <_BaseCtx>parent
                with _parent._mu:
                    if _parent._err is not None:
                        ctx._cancel(_parent._err)
                    else:
                        _parent._children.add(ctx)
            else:
                if _ready(pdone):
                    ctx._cancel(parent.err())
                else:
                    pforeignv.append(parent)

        if len(pforeignv) == 0:
            return

        # there are some foreign contexts to propagate cancel from
        def _():
            _, _rx = pyselect(
                ctx._done.recv,                         # 0
                *[_.done().recv for _ in pforeignv]     # 1 + ...
            )
            # 0. nothing - already canceled
            if _ > 0:
                ctx._cancel(pforeignv[_-1].err())
        pygo(_)


# _CancelCtx is context that can be canceled.
cdef class _CancelCtx(_BaseCtx):
    def __init__(_CancelCtx ctx, *parentv):
        super(_CancelCtx, ctx).__init__(pychan(dtype='C.structZ'), *parentv)


# _ValueCtx is context that carries key -> value.
cdef class _ValueCtx(_BaseCtx):
    # {} (key, value) specific to this context.
    # the rest of the keys are inherited from parents.
    # does not change after setup.
    cdef dict   _kv

    def __init__(_ValueCtx ctx, dict kv, parent):
        super(_ValueCtx, ctx).__init__(None, parent)
        ctx._kv         = kv

    def value(_ValueCtx ctx, object key):
        v = ctx._kv.get(key)
        if v is not None:
            return v
        return super(_ValueCtx, ctx).value(key)


# _TimeoutCtx is context that is canceled on timeout.
cdef class _TimeoutCtx(_CancelCtx):
    cdef double _deadline
    cdef object _timer      # pytime.Timer

    def __init__(_TimeoutCtx ctx, double timeout, double deadline, parent):
        super(_TimeoutCtx, ctx).__init__(parent)
        assert timeout > 0
        ctx._deadline = deadline
        ctx._timer    = pytime.after_func(timeout, lambda: ctx._cancel(pydeadlineExceeded))

    def deadline(_TimeoutCtx ctx):
        return ctx._deadline

    # cancel -> stop timer
    def _cancelFrom(_TimeoutCtx ctx, cancelFrom, err):
        super(_TimeoutCtx, ctx)._cancelFrom(cancelFrom, err)
        ctx._timer.stop()



# _ready returns whether channel ch is ready.
def _ready(pychan ch):
    _, _rx = pyselect(
            ch.recv,    # 0
            pydefault,  # 1
    )
    if _ == 0:
        return True
    if _ == 1:
        return False


# ---- for tests ----

def _tctxchildren(_BaseCtx ctx):    # -> ctx._children
    return ctx._children
