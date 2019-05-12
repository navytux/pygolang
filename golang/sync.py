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
"""Package sync mirrors Go package sync.

See the following link about Go sync package:

    https://golang.org/pkg/sync
"""

from __future__ import print_function, absolute_import

import threading, sys
from golang import go, defer, func, panic
from golang import context

import six

# Once allows to execute an action only once.
#
# For example:
#
#   once = Once()
#   ...
#   once.do(doSomething)
class Once(object):
    def __init__(once):
        once._mu    = threading.Lock()
        once._done  = False

    def do(once, f):
        with once._mu:
            if not once._done:
                once._done = True
                f()


# WaitGroup allows to wait for collection of tasks to finish.
class WaitGroup(object):
    def __init__(wg):
        wg._mu      = threading.Lock()
        wg._count   = 0
        wg._event   = threading.Event()

    def done(wg):
        wg.add(-1)

    def add(wg, delta):
        if delta == 0:
            return
        with wg._mu:
            wg._count += delta
            if wg._count < 0:
                panic("sync: negative WaitGroup counter")
            if wg._count == 0:
                wg._event.set()
                wg._event = threading.Event()

    def wait(wg):
        with wg._mu:
            if wg._count == 0:
                return
            event = wg._event
        event.wait()


# WorkGroup is a group of goroutines working on a common task.
#
# Use .go() to spawn goroutines, and .wait() to wait for all of them to
# complete, for example:
#
#   wg = WorkGroup(ctx)
#   wg.go(f1)
#   wg.go(f2)
#   wg.wait()
#
# Every spawned function accepts context related to the whole work and derived
# from ctx used to initialize WorkGroup, for example:
#
#   def f1(ctx):
#       ...
#
# Whenever a function returns error (raises exception), the work context is
# canceled indicating to other spawned goroutines that they have to cancel their
# work. .wait() waits for all spawned goroutines to complete and returns/raises
# error, if any, from the first failed subtask.
#
# WorkGroup is modelled after https://godoc.org/golang.org/x/sync/errgroup but
# is not equal to it.
class WorkGroup(object):

    def __init__(g, ctx):
        g._ctx, g._cancel = context.with_cancel(ctx)
        g._wg   = WaitGroup()
        g._mu   = threading.Lock()
        g._err  = None

    def go(g, f, *argv, **kw):
        g._wg.add(1)

        @func
        def _():
            defer(g._wg.done)

            try:
                f(g._ctx, *argv, **kw)
            except Exception as exc:
                with g._mu:
                    if g._err is None:
                        # this goroutine is the first failed task
                        g._err = exc
                        if six.PY2:
                            # py3 has __traceback__ automatically
                            exc.__traceback__ = sys.exc_info()[2]
                        g._cancel()
        go(_)

    def wait(g):
        g._wg.wait()
        g._cancel()
        if g._err is not None:
            # reraise the exception so that original traceback is there
            if six.PY3:
                raise g._err
            else:
                six.reraise(g._err, None, g._err.__traceback__)
