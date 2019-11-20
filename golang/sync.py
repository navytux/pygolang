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
"""Package sync mirrors and amends Go package sync.

 - `WorkGroup` allows to spawn group of goroutines working on a common task(*).
 - `Once` allows to execute an action only once.
 - `WaitGroup` allows to wait for a collection of tasks to finish.
 - `Sema`(*) and `Mutex` provide low-level synchronization.

See also https://golang.org/pkg/sync for Go sync package documentation.

(*) not provided in Go version.
"""

from __future__ import print_function, absolute_import

import sys
from golang import go, defer, func
from golang import context

import six

from golang._sync import \
    PySema      as Sema,        \
    PyMutex     as Mutex,       \
    PyOnce      as Once,        \
    PyWaitGroup as WaitGroup    \


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
        g._mu   = Mutex()
        g._err  = None

    def go(g, f, *argv, **kw):
        g._wg.add(1)
        go(lambda: g._run(f, *argv, **kw))

    @func
    def _run(g, f, *argv, **kw):
        defer(g._wg.done)

        try:
            f(g._ctx, *argv, **kw)
        except:
            _, exc, tb = sys.exc_info()
            with g._mu:
                if g._err is None:
                    # this goroutine is the first failed task
                    g._err = exc
                    if six.PY2:
                        # py3 has __traceback__ automatically
                        exc.__traceback__ = tb
                    g._cancel()
            exc = None
            tb  = None


    def wait(g):
        g._wg.wait()
        g._cancel()
        if g._err is not None:
            # reraise the exception so that original traceback is there
            if six.PY3:
                raise g._err
            else:
                six.reraise(g._err, None, g._err.__traceback__)
