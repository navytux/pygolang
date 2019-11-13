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

from __future__ import print_function, absolute_import

from golang._context import \
    PyContext               as Context,             \
    pybackground            as background,          \
    pycanceled              as canceled,            \
    pydeadlineExceeded      as deadlineExceeded,    \
    pywith_cancel           as with_cancel,         \
    pywith_value            as with_value,          \
    pywith_deadline         as with_deadline,       \
    pywith_timeout          as with_timeout,        \
    pymerge                 as merge
