#!/usr/bin/env python
# Copyright (C) 2021-2023  Nexedi SA and Contributors.
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
"""This program verifies signal.Notify(), Ignore() and Reset() with 'all signals' argument."""

from __future__ import print_function, absolute_import

from golang import chan
from golang import os as gos, syscall, time
from golang.os import signal
from golang.os.signal_test import killme
import sys

def main():
    # build "all signals" list
    allsigv = []
    for attr in dir(syscall):
        if attr.startswith("SIG") and "_" not in attr:
            sig = getattr(syscall, attr)
            if sig not in allsigv: # avoid e.g. SIGCHLD/SIGCLD dups
                allsigv.append(sig)
    allsigv.sort(key=lambda sig: sig.signo)
    def without(signame):
        sig = getattr(syscall, signame, None)
        if sig is not None:
            allsigv.remove(sig)
    without('SIGKILL') # SIGKILL/SIGSTOP cannot be caught
    without('SIGSTOP')
    without('SIGBUS')  # AddressSanitizer crashes on SIGBUS/SIGFPE/SIGSEGV
    without('SIGFPE')
    without('SIGSEGV')
    without('SIGILL')  # SIGILL/SIGABRT cause termination on windows
    without('SIGABRT')

    # Notify() -> kill * -> should be notified
    ch = chan(10, dtype=gos.Signal)
    signal.Notify(ch) # all signals
    for sig in allsigv:
        emit("-> %d %s" % (sig.signo, sig))
        killme(sig)
        xsig = ch.recv()
        emit("<- %d %s" % (xsig.signo, xsig))
        if xsig != sig:
            raise AssertionError("got %s, expected %s" % (xsig, sig))
    emit("ok (notify)")

    # Ignore() -> kill * -> should not be notified
    emit()
    signal.Ignore() # all signals
    assert len(ch) == 0
    for sig in allsigv:
        emit("-> %d %s" % (sig.signo, sig))
        killme(sig)
        assert len(ch) == 0
    time.sleep(0.3)
    assert len(ch) == 0
    emit("ok (ignore)")

    # Reset() -> kill * should be handled by OS by default
    emit()
    signal.Reset() # all signals
    emit("terminating ...")
    killme(syscall.SIGTERM)
    raise AssertionError("not terminated")

def emit(msg=''):
    print(msg)
    sys.stdout.flush()


if __name__ == '__main__':
    main()
