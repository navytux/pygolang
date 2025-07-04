# -*- coding: utf-8 -*-
# Copyright (C) 2021-2025  Nexedi SA and Contributors.
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

from __future__ import print_function, absolute_import

from golang import chan, func, defer
from golang import os as gos, syscall, time
from golang.os import signal
import os
from os.path import dirname

from golang.golang_test import panics, _pyrun
from pytest import raises
from subprocess import PIPE

try:
    from signal import raise_signal
except ImportError: # py2
    from _testcapi import raise_signal


# directories
dir_os       = dirname(__file__)    # .../pygolang/os
dir_testprog = dir_os + "/testprog" # .../pygolang/os/testprog


# default to use SIGUSR1/SIGUSR2 in tests.
# but use SIGTERM/SIGINT if those are not available (windows).
try:
    SIG1 = getattr(syscall, 'SIGUSR1')
    SIG2 = getattr(syscall, 'SIGUSR2')
except AttributeError:
    SIG1 = syscall.SIGTERM
    SIG2 = syscall.SIGINT


N = 1000

# test_signal verifies signal delivery to channels controlled by Notify/Stop/Ignore/Reset.
@func
def test_signal():
    # Notify/Stop with wrong chan dtype -> panic
    _ = panics("pychan: channel type mismatch")
    with _:  signal.Notify(chan(2), SIG1)
    with _:  signal.Stop  (chan(2))
    with _:  signal.Notify(chan(2, dtype='C.int'), SIG1)
    with _:  signal.Stop  (chan(2, dtype='C.int'))

    # Notify/Ignore/Reset with wrong signal type
    _ = raises(TypeError)
    with _:  signal.Notify(chan(dtype=gos.Signal), None)
    with _:  signal.Ignore(None)
    with _:  signal.Reset(None)

    # subscribe ch1(SIG1), ch12(SIG1,SIG2) and ch2(SIG2)
    ch1  = chan(2, dtype=gos.Signal)
    ch12 = chan(2, dtype=gos.Signal)
    ch2  = chan(2, dtype=gos.Signal)
    signal.Notify(ch1,  SIG1)
    signal.Notify(ch12, SIG1, SIG2)
    signal.Notify(ch2,        SIG2)
    def _():
        signal.Reset()
    defer(_)

    for i in range(N):
        # raise SIG1 -> should be delivered to ch1 and ch12
        assert len(ch1)  == 0
        assert len(ch12) == 0
        assert len(ch2)  == 0
        killme(SIG1)
        waitfor(lambda: len(ch1) == 1 and len(ch12) == 1)
        sig1  = ch1.recv()
        sig12 = ch12.recv()
        assert sig1  == SIG1
        assert sig12 == SIG1

        # raise SIG2 -> should be delivered to         ch12 and ch2
        assert len(ch1)  == 0
        assert len(ch12) == 0
        assert len(ch2)  == 0
        killme(SIG2)
        waitfor(lambda: len(ch12) == 1 and len(ch2) == 1)
        sig12 = ch12.recv()
        sig2  = ch2.recv()
        assert sig12 == SIG2
        assert sig2  == SIG2
        # if SIG2 will be eventually delivered to ch1 - it will break
        # in SIG1 check on next iteration.

    # Stop(ch2) -> signals should not be delivered to ch2 anymore
    signal.Stop(ch2)
    for i in range(N):
        # SIG1 -> ch1, ch12
        assert len(ch1)  == 0
        assert len(ch12) == 0
        assert len(ch2)  == 0
        killme(SIG1)
        waitfor(lambda: len(ch1) == 1 and len(ch12) == 1)
        sig1  = ch1.recv()
        sig12 = ch12.recv()
        assert sig1  == SIG1
        assert sig12 == SIG1

        # SIG2 -> ch12, !ch2
        assert len(ch1)  == 0
        assert len(ch12) == 0
        assert len(ch2)  == 0
        killme(SIG2)
        waitfor(lambda: len(ch12) == 1)
        sig12 = ch12.recv()
        assert sig12 == SIG2
        # if SIG2 will be eventually delivered to ch2 - it will break on
        # next iteration.

    # Ignore(SIG1) -> ch1 should not be delivered to anymore, ch12 should be delivered only SIG2
    signal.Ignore(SIG1)
    for i in range(N):
        # SIG1 -> ø
        assert len(ch1)  == 0
        assert len(ch12) == 0
        assert len(ch2)  == 0
        killme(SIG1)
        time.sleep(1E-6)

        # SIG2 -> ch12
        assert len(ch1)  == 0
        assert len(ch12) == 0
        assert len(ch2)  == 0
        killme(SIG2)
        waitfor(lambda: len(ch12) == 1)
        sig12 = ch12.recv()
        assert sig12 == SIG2
        # if SIG1 or SIG2 will be eventually delivered to ch1 or ch2 - it
        # will break on next iteration.

    # Notify after Ignore
    signal.Notify(ch1, SIG1)
    for i in range(N):
        # SIG1 -> ch1
        assert len(ch1)  == 0
        assert len(ch12) == 0
        assert len(ch2)  == 0
        killme(SIG1)
        waitfor(lambda: len(ch1) == 1)
        sig1 = ch1.recv()
        assert sig1 == SIG1

        # SIG2 -> ch12
        assert len(ch1)  == 0
        assert len(ch12) == 0
        assert len(ch2)  == 0
        killme(SIG2)
        waitfor(lambda: len(ch12) == 1)
        sig12 = ch12.recv()
        assert sig12 == SIG2
        # if SIG1 or SIG2 will be eventually delivered to wrong place -
        # it will break on next iteration.

    # Reset is tested in test_stdlib_interop (it needs non-terminating default
    # handler to verify behaviour)


# test_notify_reinstall verifies that repeated Notify correctly (re)installs _os_sighandler.
@func
def test_notify_reinstall():
    ch = chan(10, dtype=gos.Signal)
    def _():
        signal.Stop(ch)
    defer(_)

    for i in range(N):
        signal.Stop(ch)
        signal.Notify(ch, SIG1)

    time.sleep(0.1*time.second)
    assert len(ch) == 0
    killme(SIG1)
    time.sleep(0.1*time.second)
    assert len(ch) == 1


# test_signal_all verifies Notify(ø), Ignore(ø) and Reset(ø) that work on "all signals".
def test_signal_all():
    retcode, out, _ = _pyrun([dir_testprog + "/signal_test_all.py"], stdout=PIPE)
    assert b"ok (notify)"        in out
    assert b"ok (ignore)"        in out
    assert b"terminating ..."    in out
    assert retcode == (-syscall.SIGTERM.signo  if os.name != 'nt'  else 3)


# test_stdlib_interop verifies that there is minimal compatibility in between
# golang.os.signal and stdlib signal modules: signal handlers installed by
# stdlib signal, before golang.os.signal becomes used, continue to be notified
# about received signals.
#
# NOTE: it does not work the other way - stdlib signal, if used after
# golang.os.signal, will effectively disable all signal handlers installed by
# gsignal.Notify. In other words stdlib signal installs signal handlers in
# non-cooperative way.
@func
def test_stdlib_interop():
    import signal as pysig

    ch1 = chan(2, dtype=object) # NOTE not gos.Signal nor 'C.os::Signal'
    def _(signo, frame):
        ch1.send("SIG1")
    pysig.signal(SIG1.signo, _)
    def _():
        pysig.signal(SIG1.signo, pysig.SIG_IGN)
    defer(_)

    # verify that plain pysig delivery works
    for i in range(N):
        assert len(ch1) == 0
        killme(SIG1)
        waitfor(lambda: len(ch1) == 1)
        obj1 = ch1.recv()
        assert obj1 == "SIG1"

    # verify that combined pysig + golang.os.signal delivery works
    ch2 = chan(2, dtype=gos.Signal)
    signal.Notify(ch2, SIG1)
    def _():
        signal.Stop(ch2)
    defer(_)

    for i in range(N):
        assert len(ch1) == 0
        assert len(ch2) == 0
        killme(SIG1)
        waitfor(lambda: len(ch1) == 1 and len(ch2) == 1)
        obj1 = ch1.recv()
        sig2 = ch2.recv()
        assert obj1 == "SIG1"
        assert sig2 == SIG1

    # Ignore stops delivery to both pysig and golang.os.signal
    signal.Ignore(SIG1)
    for i in range(N):
        assert len(ch1) == 0
        assert len(ch2) == 0
        killme(SIG1)
        time.sleep(1E-6)
    time.sleep(0.1) # just in case
    assert len(ch1) == 0
    assert len(ch2) == 0

    # after Reset pysig delivery is restored even after Ignore
    signal.Reset(SIG1)
    for i in range(N):
        assert len(ch1) == 0
        assert len(ch2) == 0
        killme(SIG1)
        waitfor(lambda: len(ch1) == 1)
        assert len(ch2) == 0
        obj1 = ch1.recv()
        assert obj1 == "SIG1"

    # Reset stops delivery to golang.os.signal and restores pysig delivery
    signal.Notify(ch2, SIG1)
    signal.Reset(SIG1)
    for i in range(N):
        assert len(ch1) == 0
        assert len(ch2) == 0
        killme(SIG1)
        waitfor(lambda: len(ch1) == 1)
        assert len(ch2) == 0
        obj1 = ch1.recv()
        assert obj1 == "SIG1"


# test_stdlib_interop_KeyboardInterrupt verifies that signal.{Notify,Ignore} disable
# raising KeyboardInterrupt by default on SIGINT and signal.{Stop,Reset} reenable it back.
@func
def test_stdlib_interop_KeyboardInterrupt():
    # KeyboardInterrupt is raised by default
    with raises(KeyboardInterrupt):
        killme(syscall.SIGINT)
        time.sleep(1)

    ch1 = chan(2, dtype=gos.Signal)
    ch2 = chan(2, dtype=gos.Signal)
    def _():
        signal.Reset(syscall.SIGINT)
    defer(_)

    # Notify disables raising KeyboardInterrupt by default on SIGINT
    signal.Notify(ch1, syscall.SIGINT)
    try:
        killme(syscall.SIGINT)
        waitfor(lambda: len(ch1) == 1)
        obj1 = ch1.recv()
        assert obj1 == syscall.SIGINT
        time.sleep(0.1) # just in case
    except KeyboardInterrupt:
        raise AssertionError("KeyboardInterrupt raised after signal.Notify +ch1")

    signal.Notify(ch2, syscall.SIGINT)
    try:
        killme(syscall.SIGINT)
        waitfor(lambda: len(ch1) == 1 and len(ch2) == 1)
        obj1 = ch1.recv()
        obj2 = ch2.recv()
        assert obj1 == syscall.SIGINT
        assert obj2 == syscall.SIGINT
        time.sleep(0.1) # just in case
    except KeyboardInterrupt:
        raise AssertionError("KeyboardInterrupt raised after signal.Notify +ch1 +ch2")

    # last Stop should reenable raising KeyboardInterrupt by default on SIGINT
    signal.Stop(ch1)
    try:
        killme(syscall.SIGINT)
        waitfor(lambda: len(ch2) == 1)
        obj2 = ch2.recv()
        assert obj2 == syscall.SIGINT
        time.sleep(0.1) # just in case
        assert len(ch1) == 0
    except KeyboardInterrupt:
        raise AssertionError("KeyboardInterrupt raised after signal.Notify +ch1 +ch2 -ch1")

    signal.Stop(ch2)
    with raises(KeyboardInterrupt):
        killme(syscall.SIGINT)
        time.sleep(1)
    time.sleep(0.1) # just in case
    assert len(ch1) == 0
    assert len(ch2) == 0

    # Ignore disables raising KeyboardInterrupt by default on SIGINT
    signal.Ignore(syscall.SIGINT)
    try:
        killme(syscall.SIGINT)
        time.sleep(0.1)
        assert len(ch1) == 0
        assert len(ch2) == 0
    except KeyboardInterrupt:
        raise AssertionError("KeyboardInterrupt raised after signal.Ignore")

    # Reset restores original behaviour
    signal.Reset(syscall.SIGINT)
    with raises(KeyboardInterrupt):
        killme(syscall.SIGINT)
        time.sleep(1)
    time.sleep(0.1) # just in case
    assert len(ch1) == 0
    assert len(ch2) == 0



# killme sends signal sig to own process.
def killme(sig):
    # use raise(sig) instead of kill(mypid, sig) so that it works on windows,
    # where os.kill unconditionally terminates target process.
    raise_signal(sig.signo)

# waitfor waits until cond() becomes true or timeout.
def waitfor(cond):
    tstart = time.now()
    while 1:
        if cond():
            return
        t = time.now()
        if (t - tstart) > 1*time.second:
            raise AssertionError("timeout waiting")
        time.sleep(1E-6) # NOTE sleep(0) consumes lot of CPU under gevent
