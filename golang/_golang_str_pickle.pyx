# -*- coding: utf-8 -*-
# Copyright (C) 2023-2024  Nexedi SA and Contributors.
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
"""_golang_str_pickle.pyx complements _golang_str.pyx and keeps everything
related to pickling strings.

It is included from _golang_str.pyx .
"""

if PY_MAJOR_VERSION >= 3:
    import copyreg as pycopyreg
else:
    import copy_reg as pycopyreg

cdef object zbinary  # = zodbpickle.binary | None
try:
    import zodbpickle
except ImportError:
    zbinary = None
else:
    zbinary = zodbpickle.binary


# support for pickling bstr/ustr as standalone types.
#
# pickling is organized in such a way that
# - what is saved by py2 can be loaded correctly on both py2/py3,  and similarly
# - what is saved by py3 can be loaded correctly on both py2/py3   as well.
cdef _bstr__reduce_ex__(self, protocol):
    # Ideally we want to emit bstr(BYTES), but BYTES is not available for
    # protocol < 3. And for protocol < 3 emitting bstr(STRING) is not an
    # option because plain py3 raises UnicodeDecodeError on loading arbitrary
    # STRING data. However emitting bstr(UNICODE) works universally because
    # pickle supports arbitrary unicode - including invalid unicode - out of
    # the box and in exactly the same way on both py2 and py3. For the
    # reference upstream py3 uses surrogatepass on encode/decode UNICODE data
    # to achieve that.
    if protocol < 3:
        # use UNICODE for data
        udata = _udata(pyu(self))
        if protocol < 2:
            return (self.__class__, (udata,))   # bstr UNICODE REDUCE
        else:
            return (pycopyreg.__newobj__,
                    (self.__class__, udata))    # bstr UNICODE NEWOBJ
    else:
        # use BYTES for data
        bdata = _bdata(self)
        if PY_MAJOR_VERSION < 3:
            # the only way we can get here on py2 and protocol >= 3 is zodbpickle
            # -> similarly to py3 save bdata as BYTES
            assert zbinary is not None
            bdata = zbinary(bdata)
        return (
            pycopyreg.__newobj__,               # bstr BYTES   NEWOBJ
            (self.__class__, bdata))

cdef _ustr__reduce_ex__(self, protocol):
    # emit ustr(UNICODE).
    # TODO later we might want to switch to emitting ustr(BYTES)
    #      even if we do this, it should be backward compatible
    if protocol < 2:
        return (self.__class__, (_udata(self),))# ustr UNICODE REDUCE
    else:
        return (pycopyreg.__newobj__,           # ustr UNICODE NEWOBJ
                (self.__class__, _udata(self)))
