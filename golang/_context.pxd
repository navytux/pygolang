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
"""Package context mirrors and amends Go package context.

 - `Context` represents operational context that carries deadline, cancellation
   signal and immutable context-local key -> value dict.
 - `background` returns empty context that is never canceled.
 - `with_cancel` creates new context that can be canceled on its own.
 - `with_deadline` creates new context with deadline.
 - `with_timeout` creates new context with timeout.
 - `with_value` creates new context with attached key=value.
 - `merge` creates new context from 2 parents(*).

See also https://golang.org/pkg/context for Go context package documentation.
See also https://blog.golang.org/context for overview.

(*) not provided in Go version.
"""

from golang cimport chan, structZ, error, refptr, interface, Nil
from golang cimport cxx
from libcpp.utility cimport pair

# XXX for std::function cython does not provide operator() and =nullptr
#from libcpp.functional cimport function
#ctypedef function[void()] cancelFunc
cdef extern from "golang/libgolang.h" namespace "golang" nogil:
    cppclass cancelFunc "golang::func<void()>":
        void operator() ()
        void operator= (Nil)

cdef extern from "golang/context.h" namespace "golang::context" nogil:
    cppclass _Context:
        double          deadline()
        chan[structZ]   done()
        error           err()
        interface       value(const void *key)

    cppclass Context (refptr[_Context]):
        # Context.X = Context->X in C++
        double          deadline    "_ptr()->deadline"  ()
        chan[structZ]   done        "_ptr()->done"      ()
        error           err         "_ptr()->err"       ()
        interface       value       "_ptr()->value"     (const void *key)

    Context background()
    error   canceled
    error   deadlineExceeded

    pair[Context, cancelFunc] with_cancel   (Context parent)
    Context                   with_value    (Context parent, const void *key, interface value)
    pair[Context, cancelFunc] with_deadline (Context parent, double deadline)
    pair[Context, cancelFunc] with_timeout  (Context parent, double timeout)
    pair[Context, cancelFunc] merge         (Context parent1, Context parent2)

    # for testing
    cxx.set[Context] _tctxchildren(Context ctx)


# ---- python bits ----

from golang cimport pychan
from cython cimport final

@final
cdef class PyContext:
    cdef Context  ctx
    cdef pychan   _pydone # pychan wrapping ctx.done()

    # PyContext.from_ctx returns PyContext wrapping pyx/nogil-level Context ctx.
    @staticmethod
    cdef PyContext from_ctx (Context ctx)
