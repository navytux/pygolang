#ifndef _NXD_LIBGOLANG_CONTEXT_H
#define _NXD_LIBGOLANG_CONTEXT_H

// Copyright (C) 2019  Nexedi SA and Contributors.
//                     Kirill Smelkov <kirr@nexedi.com>
//
// This program is free software: you can Use, Study, Modify and Redistribute
// it under the terms of the GNU General Public License version 3, or (at your
// option) any later version, as published by the Free Software Foundation.
//
// You can also Link and Combine this program with other software covered by
// the terms of any of the Free Software licenses or any of the Open Source
// Initiative approved licenses and Convey the resulting work. Corresponding
// source of such a combination shall include the source code for all other
// software used.
//
// This program is distributed WITHOUT ANY WARRANTY; without even the implied
// warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
//
// See COPYING file for full licensing terms.
// See https://www.nexedi.com/licensing for rationale and options.

// Package context mirrors and amends Go package context.
//
//  - `Context` represents operational context that carries deadline, cancellation
//    signal and immutable context-local key -> value dict.
//  - `background` returns empty context that is never canceled.
//  - `with_cancel` creates new context that can be canceled on its own.
//  - `with_deadline` creates new context with deadline.
//  - `with_timeout` creates new context with timeout.
//  - `with_value` creates new context with attached key=value.
//  - `merge` creates new context from 2 parents(*).
//
// See also https://golang.org/pkg/context for Go context package documentation.
// See also https://blog.golang.org/context for overview.
//
// (*) not provided in Go version.

#include <golang/libgolang.h>
#include <golang/cxx.h>

// golang::context::
namespace golang {
namespace context {

// Context is the interface that every context must implement.
//
// A context carries deadline, cancellation signal and immutable context-local
// key -> value dict.
struct _Context : _interface {
    // deadline() returns context deadline or +inf, if there is no deadline.
    virtual double deadline()           = 0;  // -> time | INFINITY

    // done returns channel that is closed when the context is canceled.
    virtual chan<structZ> done()        = 0;

    // err returns nil if done is not yet closed, or error that explains why context was canceled.
    virtual error err()                 = 0;

    // value returns value associated with key, or nil, if context has no key.
    virtual interface value(const void *key)   = 0;  // -> value | nil
};
typedef refptr<_Context> Context;

// background returns empty context that is never canceled.
LIBGOLANG_API Context background();

// canceled is the error returned by Context.err when context is canceled.
extern LIBGOLANG_API const global<error> canceled;

// deadlineExceeded is the error returned by Context.err when time goes past context's deadline.
extern LIBGOLANG_API const global<error> deadlineExceeded;

// with_cancel creates new context that can be canceled on its own.
//
// Returned context inherits from parent and in particular is canceled when
// parent is done.
//
// The caller should explicitly call cancel to release context resources as soon
// the context is no longer needed.
LIBGOLANG_API std::pair<Context, func<void()>>
    with_cancel(Context parent); // -> ctx, cancel

// with_value creates new context with key=value.
//
// Returned context inherits from parent and in particular has all other
// (key, value) pairs provided by parent.
LIBGOLANG_API Context
    with_value(Context parent, const void *key, interface value); // -> ctx

// with_deadline creates new context with deadline.
//
// The deadline of created context is the earliest of provided deadline or
// deadline of parent. Created context will be canceled when time goes past
// context deadline or cancel called, whichever happens first.
//
// The caller should explicitly call cancel to release context resources as soon
// the context is no longer needed.
LIBGOLANG_API std::pair<Context, func<void()>>
    with_deadline(Context parent, double deadline); // -> ctx, cancel

// with_timeout creates new context with timeout.
//
// it is shorthand for with_deadline(parent, now+timeout).
LIBGOLANG_API std::pair<Context, func<void()>>
    with_timeout(Context parent, double timeout); // -> ctx, cancel

// merge merges 2 contexts into 1.
//
// The result context:
//
//   - is done when parent1 or parent2 is done, or cancel called, whichever happens first,
//   - has deadline = min(parent1.Deadline, parent2.Deadline),
//   - has associated values merged from parent1 and parent2, with parent1 taking precedence.
//
// Canceling this context releases resources associated with it, so code should
// call cancel as soon as the operations running in this Context complete.
//
// Note: on Go side merge is not part of stdlib context and is provided by
// https://godoc.org/lab.nexedi.com/kirr/go123/xcontext#hdr-Merging_contexts
LIBGOLANG_API std::pair<Context, func<void()>>
    merge(Context parent1, Context parent2);  // -> ctx, cancel

// for testing
LIBGOLANG_API cxx::set<Context> _tctxchildren(Context ctx);

}}   // golang::context::

#endif  // _NXD_LIBGOLANG_CONTEXT_H
