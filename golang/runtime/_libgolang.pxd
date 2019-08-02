# cython: language_level=2
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
"""pyx declarations for libgolang bits that are only interesting for runtimes"""

cdef extern from "golang/golang.h" nogil:
    struct _libgolang_sema
    struct _libgolang_runtime_ops:
        _libgolang_sema* (*sema_alloc)  ()
        void             (*sema_free)   (_libgolang_sema*)
        void             (*sema_acquire)(_libgolang_sema*)
        void             (*sema_release)(_libgolang_sema*)