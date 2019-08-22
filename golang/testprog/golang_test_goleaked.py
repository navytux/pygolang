#!/usr/bin/env python
# Copyright (C) 2018-2019  Nexedi SA and Contributors.
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
"""This program tests that leaked goroutines don't prevent program to exit."""

from __future__ import print_function, absolute_import

from golang import go, chan
from golang import time
import os, sys


def main():
    ng = 100    # N(tasks) to spawn
    gstarted = chan()   # main <- g
    mainexit = chan()   # main -> all g

    # a task that wants to live longer than main
    def leaktask():
        gstarted.send(1)
        mainexit.recv()

        # normally when main thread exits, the whole process is terminated.
        # however if go spawns a thread with daemon=0, we are left here to continue.
        # make sure it is not the case
        time.sleep(3)
        print("leaked goroutine: process did not terminate", file=sys.stderr)
        sys.stderr.flush()
        time.sleep(1)
        os._exit(1) # not sys.exit - that can be used only from main thread

    for i in range(ng):
        go(leaktask)

    # make sure all tasks are started
    for i in range(ng):
        gstarted.recv()

    # now we can exit
    mainexit.close()
    sys.exit(0)


if __name__ == '__main__':
    main()
