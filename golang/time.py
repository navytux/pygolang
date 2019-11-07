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
"""Package time mirrors Go package time.

 - `now` returns current time.
 - `sleep` pauses current task.
 - `Ticker` and `Timer` provide timers integrated with channels.
 - `tick`, `after` and `after_func` are convenience wrappers to use
   tickers and timers easily.

See also https://golang.org/pkg/time for Go time package documentation.
"""

from __future__ import print_function, absolute_import

from golang._time import \
    pysecond        as second,      \
    pynanosecond    as nanosecond,  \
    pymicrosecond   as microsecond, \
    pymillisecond   as millisecond, \
    pyminute        as minute,      \
    pyhour          as hour,        \
 \
    pynow       as now,     \
    pysleep     as sleep,   \
 \
    pytick          as tick,        \
    pyafter         as after,       \
    pyafter_func    as after_func,  \
    PyTicker        as Ticker,      \
    PyTimer         as Timer
