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

from golang import sync, go, chan, _PanicError
import time
from pytest import raises

def test_once():
    once = sync.Once()
    l = []
    def _():
        l.append(1)

    once.do(_)
    assert l == [1]
    once.do(_)
    assert l == [1]
    once.do(_)
    assert l == [1]

    once = sync.Once()
    l = []
    def _():
        l.append(2)
        raise RuntimeError()

    with raises(RuntimeError):
        once.do(_)
    assert l == [2]
    once.do(_)  # no longer raises
    assert l == [2]
    once.do(_)  # no longer raises
    assert l == [2]


def test_waitgroup():
    wg = sync.WaitGroup()
    wg.add(2)

    ch = chan(3)
    def _():
        wg.wait()
        ch.send('a')
    for i in range(3):
        go(_)

    wg.done()
    assert len(ch) == 0
    time.sleep(0.1)
    assert len(ch) == 0
    wg.done()

    for i in range(3):
        assert ch.recv() == 'a'

    wg.add(1)
    go(_)
    time.sleep(0.1)
    assert len(ch) == 0
    wg.done()
    assert ch.recv() == 'a'

    with raises(_PanicError):
        wg.done()
