# cython: language_level=2
# Copyright (C) 2019-2020  Nexedi SA and Contributors.
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
"""Package sync mirrors and amends Go package sync.

 - `WorkGroup` allows to spawn group of goroutines working on a common task(*).
 - `Once` allows to execute an action only once.
 - `WaitGroup` allows to wait for a collection of tasks to finish.
 - `Sema`(*), `Mutex` and `RWMutex` provide low-level synchronization.

See also https://golang.org/pkg/sync for Go sync package documentation.

(*) not provided in Go standard library, but package
    https://godoc.org/lab.nexedi.com/kirr/go123/xsync
    provides corresponding Go equivalents.
"""

from golang cimport error, refptr
from golang cimport context

cdef extern from "golang/sync.h" namespace "golang::sync" nogil:
    cppclass Sema:
        Sema()
        void acquire()
        void release()

    cppclass Mutex:
        void lock()
        void unlock()

    cppclass RWMutex:
        void Lock()
        void Unlock()
        void RLock()
        void RUnlock()
        void UnlockToRLock()

    cppclass Once:
        void do "do_" (...)     # ... = func<void()>

    cppclass WaitGroup:
        void done()
        void add(int delta)
        void wait()

    # WorkGroup
    cppclass _WorkGroup:
        void  go(...)                       # ... = func<error(context::Context)>
        error wait()

    cppclass WorkGroup (refptr[_WorkGroup]):
        # WorkGroup.X = WorkGroup->X in C++.
        void  go    "_ptr()->go"    (...)   # ... = func<error(context::Context)>
        error wait  "_ptr()->wait"  ()

    WorkGroup NewWorkGroup(context.Context ctx)
