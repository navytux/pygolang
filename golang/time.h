#ifndef _NXD_LIBGOLANG_TIME_H
#define	_NXD_LIBGOLANG_TIME_H

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

// Package time mirrors Go package time.
//
//  - `now` returns current time.
//  - `sleep` pauses current task.
//
// See also https://golang.org/pkg/time for Go time package documentation.
//
//
// C-level API
//
// Subset of time package functionality is also provided via C-level API:
//
//  - `_tasknanosleep` pauses current task.
//  - `_nanotime` returns current time.


#include <golang/libgolang.h>


// ---- C-level API ----

#ifdef __cplusplus
namespace golang {
namespace time {
extern "C" {
#endif

LIBGOLANG_API void _tasknanosleep(uint64_t dt);
LIBGOLANG_API uint64_t _nanotime(void);

#ifdef __cplusplus
}}} // golang::time:: "C"
#endif


// ---- C++ API ----

#ifdef __cplusplus

// golang::time::
namespace golang {
namespace time {

// sleep pauses current goroutine for at least dt seconds.
LIBGOLANG_API void sleep(double dt);

// now returns current time in seconds.
LIBGOLANG_API double now();

}}   // golang::time::
#endif  // __cplusplus

#endif	// _NXD_LIBGOLANG_TIME_H
