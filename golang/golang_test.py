# -*- coding: utf-8 -*-
# Copyright (C) 2018  Nexedi SA and Contributors.
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

from golang import go, chan, select, default, _PanicError
from pytest import raises
import time, threading

# tdelay delays a bit.
#
# XXX needed in situations when we need to start with known ordering but do not
# have a way to wait properly for ordering event.
def tdelay():
    time.sleep(1E-3)    # 1ms


def test_chan():
    # sync: pre-close vs send/recv
    ch = chan()
    ch.close()
    assert ch.recv()    == None
    assert ch.recv_()   == (None, False)
    assert ch.recv_()   == (None, False)
    raises(_PanicError, "ch.send(0)")
    raises(_PanicError, "ch.close()")

    # sync: send vs recv
    ch = chan()
    def _():
        ch.send(1)
        assert ch.recv() == 2
        ch.close()
    go(_)
    assert ch.recv() == 1
    ch.send(2)
    assert ch.recv_() == (None, False)
    assert ch.recv_() == (None, False)

    # sync: close vs send
    ch = chan()
    def _():
        tdelay()
        ch.close()
    go(_)
    raises(_PanicError, "ch.send(0)")

    # close vs recv
    ch = chan()
    def _():
        tdelay()
        ch.close()
    go(_)
    assert ch.recv_() == (None, False)

    # sync: close vs multiple recv
    ch = chan()
    done = chan()
    mu = threading.Lock()
    s  = set()
    def _():
        assert ch.recv_() == (None, False)
        with mu:
            x = len(s)
            s.add(x)
        done.send(x)
    for i in range(3):
        go(_)
    ch.close()
    for i in range(3):
        done.recv()
    assert s == {0,1,2}

    # buffered
    ch = chan(3)
    done = chan()
    for _ in range(2):
        for i in range(3):
            assert len(ch) == i
            ch.send(i)
            assert len(ch) == i+1
        for i in range(3):
            assert ch.recv_() == (i, True)

    assert len(ch) == 0
    for i in range(3):
        ch.send(i)
    assert len(ch) == 3
    def _():
        tdelay()
        assert ch.recv_() == (0, True)
        done.send('a')
        for i in range(1,4):
            assert ch.recv_() == (i, True)
        assert ch.recv_() == (None, False)
        done.send('b')
    go(_)
    ch.send(3)  # will block without receiver
    assert done.recv() == 'a'
    ch.close()
    assert done.recv() == 'b'


def test_select():
    # non-blocking try send: not ok
    ch = chan()
    _, _rx = select(
            (ch.send, 0),
            default,
    )
    assert (_, _rx) == (1, None)

    # non-blocking try recv: not ok
    _, _rx = select(
            ch.recv,
            default,
    )
    assert (_, _rx) == (1, None)

    _, _rx = select(
            ch.recv_,
            default,
    )
    assert (_, _rx) == (1, None)

    # non-blocking try send: ok
    ch = chan()
    done = chan()
    def _():
        i = 0
        while 1:
            x = ch.recv()
            if x == 'stop':
                break
            assert x == i
            i += 1
        done.close()
    go(_)

    for i in range(10):
        tdelay()
        _, _rx = select(
                (ch.send, i),
                default,
        )
        assert (_, _rx) == (0, None)
    ch.send('stop')
    done.recv()

    # non-blocking try recv: ok
    ch = chan()
    done = chan()
    def _():
        for i in range(10):
            ch.send(i)
        done.close()
    go(_)

    for i in range(10):
        tdelay()
        if i % 2:
            _, _rx = select(
                    ch.recv,
                    default,
            )
            assert (_, _rx) == (0, i)
        else:
            _, _rx = select(
                    ch.recv_,
                    default,
            )
            assert (_, _rx) == (0, (i, True))
    done.recv()


    # blocking 2·send
    ch1 = chan()
    ch2 = chan()
    done = chan()
    def _():
        tdelay()
        assert ch1.recv() == 'a'
        done.close()
    go(_)

    _, _rx = select(
        (ch1.send, 'a'),
        (ch2.send, 'b'),
    )
    assert (_, _rx) == (0, None)
    done.recv()
    assert len(ch1._sendq) == len(ch1._recvq) == 0
    assert len(ch2._sendq) == len(ch2._recvq) == 0


    # blocking 2·recv
    ch1 = chan()
    ch2 = chan()
    done = chan()
    def _():
        tdelay()
        ch1.send('a')
        done.close()
    go(_)

    _, _rx = select(
        ch1.recv,
        ch2.recv,
    )
    assert (_, _rx) == (0, 'a')
    done.recv()
    assert len(ch1._sendq) == len(ch1._recvq) == 0
    assert len(ch2._sendq) == len(ch2._recvq) == 0


    # blocking send/recv
    ch1 = chan()
    ch2 = chan()
    done = chan()
    def _():
        tdelay()
        assert ch1.recv() == 'a'
        done.close()
    go(_)

    _, _rx = select(
        (ch1.send, 'a'),
        ch2.recv,
    )
    assert (_, _rx) == (0, None)
    done.recv()
    assert len(ch1._sendq) == len(ch1._recvq) == 0
    assert len(ch2._sendq) == len(ch2._recvq) == 0


    # blocking recv/send
    ch1 = chan()
    ch2 = chan()
    done = chan()
    def _():
        tdelay()
        ch1.send('a')
        done.close()
    go(_)

    _, _rx = select(
        ch1.recv,
        (ch2.send, 'b'),
    )
    assert (_, _rx) == (0, 'a')
    done.recv()
    assert len(ch1._sendq) == len(ch1._recvq) == 0
    assert len(ch2._sendq) == len(ch2._recvq) == 0


    # buffered ping-pong
    ch = chan(1)
    for i in range(10):
        _, _rx = select(
            (ch.send, i),
            ch.recv,
        )
        assert _    == (i % 2)
        assert _rx  == (i - 1 if i % 2 else None)


    # select vs select
    for i in range(10):
        ch1 = chan()
        ch2 = chan()
        done = chan()
        def _():
            _, _rx = select(
                (ch1.send, 'a'),
                (ch2.send, 'xxx2'),
            )
            assert (_, _rx) == (0, None)

            _, _rx = select(
                (ch1.send, 'yyy2'),
                ch2.recv,
            )
            assert (_, _rx) == (1, 'b')

            done.close()

        go(_)

        _, _rx = select(
            ch1.recv,
            (ch2.send, 'xxx1'),
        )
        assert (_, _rx) == (0, 'a')

        _, _rx = select(
            (ch1.send, 'yyy1'),
            (ch2.send, 'b'),
        )
        assert (_, _rx) == (1, None)

        done.recv()
        assert len(ch1._sendq) == len(ch1._recvq) == 0
        assert len(ch2._sendq) == len(ch2._recvq) == 0
