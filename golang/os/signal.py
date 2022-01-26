# -*- coding: utf-8 -*-
# Copyright (C) 2021-2022  Nexedi SA and Contributors.
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
"""Package signal mirrors Go package signal.

 - `Notify` arranges for signals to be delivered to channels.
 - `Stop` unsubscribes a channel from signal delivery.
 - `Ignore` requests signals to be ignored.
 - `Reset` requests signals to be handled as by default.

See also https://golang.org/pkg/os/signal for Go signal package documentation.
"""

from __future__ import print_function, absolute_import

from golang.os._signal import \
    PyNotify        as Notify,      \
    PyStop          as Stop,        \
    PyIgnore        as Ignore,      \
    PyReset         as Reset
