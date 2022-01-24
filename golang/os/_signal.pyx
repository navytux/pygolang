# -*- coding: utf-8 -*-
# cython: language_level=2
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
"""_signal.pyx implements signal.pyx - see _signal.pxd for package overview."""

from __future__ import print_function, absolute_import

from golang cimport pychan, topyexc
from golang cimport os

from libc.signal cimport SIGINT
from libcpp.vector cimport vector

# adjust Python behaviour to not raise KeyboardInterrupt on SIGINT by default
# if any Notify(SIGINT) is currently active.
cdef set _pyint_notifying = set() # {pychan}
cdef _pydefault_int_handler(sig, frame):
    # with gil:
    if 1:
        if len(_pyint_notifying) != 0:
            return
    raise KeyboardInterrupt
import signal as pysignal
if pysignal.getsignal(SIGINT) is pysignal.default_int_handler:
    pysignal.default_int_handler = _pydefault_int_handler
    pysignal.signal(SIGINT, _pydefault_int_handler)


def PyNotify(pychan pych, *pysigv):
    cdef chan[os.Signal]  ch = pychan_osSignal_pyexc(pych)
    sigv, has_sigint = _unwrap_pysigv(pysigv)
    # with gil:
    if 1:
        if has_sigint:
            _pyint_notifying.add(pych)
    _Notify_pyexc(ch, sigv)


def PyStop(pychan pych):
    cdef chan[os.Signal]  ch  = pychan_osSignal_pyexc(pych)
    # with gil:
    if 1:
        try:
            _pyint_notifying.remove(pych)
        except KeyError:
            pass
    _Stop_pyexc(ch)


def PyIgnore(*pysigv):
    sigv, has_sigint = _unwrap_pysigv(pysigv)
    # with gil:
    if 1:
        if has_sigint:
            _pyint_notifying.clear()
    _Ignore_pyexc(sigv)


def PyReset(*pysigv):
    sigv, has_sigint = _unwrap_pysigv(pysigv)
    # with gil:
    if 1:
        if has_sigint:
            _pyint_notifying.clear()
    _Reset_pyexc(sigv)


# _unwrap_pysigv converts pysigv to sigv.
cdef (vector[os.Signal], bint) _unwrap_pysigv(pysigv) except *: # (sigv, has_sigint)
    cdef vector[os.Signal] sigv
    cdef bint has_sigint = (len(pysigv) == 0) # if all signals
    for xpysig in pysigv:
        if not isinstance(xpysig, os.PySignal):
            raise TypeError("expect os.Signal, got %r" % (xpysig,))
        pysig = <os.PySignal>xpysig
        sigv.push_back(pysig.sig)
        if pysig.sig.signo == SIGINT:
            has_sigint = True
    return (sigv, has_sigint)



cdef:

    chan[os.Signal] pychan_osSignal_pyexc(pychan pych)                      except +topyexc:
        return pych._chan_osSignal()

    void _Notify_pyexc(chan[os.Signal] ch, const vector[os.Signal]& sigv)   except +topyexc:
        Notify(ch, sigv)

    void _Stop_pyexc(chan[os.Signal] ch)                                    except +topyexc:
        Stop(ch)

    void _Ignore_pyexc(const vector[os.Signal]& sigv)                       except +topyexc:
        Ignore(sigv)

    void _Reset_pyexc(const vector[os.Signal]& sigv)                        except +topyexc:
        Reset(sigv)
