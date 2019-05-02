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
"""Package errgroup mirrors Go package errgroup

See the following link for errgroup documentation:

    https://godoc.org/golang.org/x/sync/errgroup
"""

from golang import go, defer, func
from golang import sync, context

# Group is a group of goroutines working on a common task.
#
# XXX canceled.
class Group(object):
    def __init__(g):
        g._wg     = sync.WaitGroup()
        g._mu     = threading.Lock()
        g._err    = None
        g._cancel = lambda:

    def go(g, f):
        g._wg.add(1)

        @func
        def _():
            defer(g._wg.done)

            try:
                f()
            except Exception e:
                with g._mu:
                    if g._err is None:
                        g._err = e      # XXX + traceback
                        g._cancel()
        go(_)

    def wait(g):
        g._wg.wait()
        if g._err is not None:
            raise g._err    # XXX raise from


def with_context(ctx):
    ctx, cancel = context.with_cancel(ctx)
    g = Group()
    g._cancel = cancel
    return g
