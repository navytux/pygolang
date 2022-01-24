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
"""_os.pyx implements os.pyx - see _os.pxd for package overview."""

from __future__ import print_function, absolute_import

from golang cimport __pystr
from cython cimport final


# Signal represents an OS signal.
@final
cdef class PySignal:

    dtype = "C.os::Signal"

    @staticmethod
    cdef PySignal from_sig(Signal sig):
        cdef PySignal pysig = PySignal.__new__(PySignal)
        pysig.sig = sig
        return pysig

    property signo:
        def __get__(PySignal pysig):
            return pysig.sig.signo

    def __str__(PySignal pysig):
        return __pystr(pysig.sig.String())

    def __repr__(PySignal pysig):
        return ("os.Signal(%d)" % pysig.sig.signo)

    # PySignal == PySignal
    def __hash__(PySignal pysig):
        return <Py_hash_t>pysig.sig.signo
    # NOTE __ne__ not needed: PySignal does not have base class and for that
    # case cython automatically generates __ne__ based on __eq__.
    def __eq__(PySignal a, object rhs):
        if not isinstance(rhs, PySignal):
            return False
        cdef PySignal b = rhs
        return (a.sig == b.sig)


def _PySignal_from_int(int signo): # -> PySignal
    return PySignal.from_sig(_Signal_from_int(signo))
