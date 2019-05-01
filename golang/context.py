# -*- coding: utf-8 -*-
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
"""Package context mirrors Go package context

XXX link to go
"""

from __future__ import print_function

from golang import chan
import threading

# Context is XXX
class Context(object):
    # done returns channel that is closed when the context is canceled.
    def done(ctx):  # -> chan
        raise NotImplementedError()

    # err returns None if done is not yet closed, or error that explains why context was canceled.
    def err(ctx):   # -> error
        raise NotImplementedError()

    # TODO:
    # .deadline()
    # .value(key)


# background returns empty context that is never canceled.
def background():   # -> Context
    return  _background

# canceled is the error returned by Context.err when context is canceled.
canceled = RuntimeError("context canceled")  # XXX ok?


# XXX
def with_cancel(parent): # -> ctx, cancel
    ctx = _Context()
    def cancel():
        ctx._cancel(None)

    # XXX background
    # XXX non _Context !ø parent

    with parent._mu:
        if parent._err is not None:
            cancel()
        else:
            parent._children.add(ctx)
            ctx._parents.add(parent)

    return ctx, cancel


# --------

# XXX
class _Background(object):
    def done(bg):
        return None # XXX -> nil chan

    def err(bg):
        return None

_background = _Background()

# _Context implements Context ... XXX
class _Context(object):
    def __init__(ctx):  # XXX + parent?
        ctx._mu         = threading.Lock()
        ctx._children   = set()             # contexts that are children of this context
        ctx._parents    = set()             # contexts that are parents of this context
        ctx._err        = None

        ctx._done       = chan()

    def done(ctx):
        return ctx._done

    def err(ctx):
        with ctx._mu:
            return ctx._err

    def _cancel(ctx, cancelFrom):
        with ctx._mu:
            if ctx._err is not None:
                return  # already canceled

            ctx._err = canceled
            children = ctx._children;   ctx._children = set()
            parents  = ctx._parents;    ctx._parents  = set()

        ctx._done.close()

        for parent in parents:
            if parent is cancelFrom:
                continue
            with parent._mu:
                if ctx in parent._children:
                    parent._children.remove(ctx)

        for child in children:
            child._cancel(ctx)
