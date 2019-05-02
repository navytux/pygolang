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
"""Package sync mirrors Go package sync

See the following link about Go sync package:

    https://golang.org/pkg/sync
"""

import threading

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
