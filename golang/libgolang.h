#ifndef _NXD_LIBGOLANG_H
#define _NXD_LIBGOLANG_H

// Copyright (C) 2018-2019  Nexedi SA and Contributors.
//                          Kirill Smelkov <kirr@nexedi.com>
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

// Library Libgolang provides Go-like features for C and C++.
//
// Library Libgolang provides Go-like
// features. The library consists of high-level type-safe C++ API,
// and low-level unsafe C API.
//
// The primary motivation for Libgolang is to serve as runtime for golang.pyx -
// - Cython part of Pygolang project. However Libgolang is independent of
// Python and should be possible to use in standalone C/C++ projects.
//
// Brief description of Libgolang API follows:
//
// C++-level API
//
//  - `sleep` pauses current task.
//  - `panic` throws exception that represent C-level panic.
//
// For example:
//
//      if (<bug condition>)
//          panic("bug");
//
//
// C-level API
//
//  - `tasknanosleep` pauses current task.
//
//
// Runtimes
//
// Libgolang, before being used, must be initialized with particular runtime
// plugin, which tailors Libgolang to particular execution environment. See
// `_libgolang_init` and `_libgolang_runtime_ops` for description of a runtime.
//
// Pygolang - the parent project of Libgolang - comes with two Libgolang runtimes:
//
//  - "thread" - a runtime that is based on OS threads, and
//  - "gevent" - a runtime that is based on greenlet and gevent.
//
// Once again, Libgolang itself is independent from Python, and other runtimes
// are possible.

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

// DSO symbols visibility (based on https://gcc.gnu.org/wiki/Visibility)
#if defined _WIN32 || defined __CYGWIN__
  #ifdef BUILDING_LIBGOLANG
    #define LIBGOLANG_API __declspec(dllexport)
  #else
    #define LIBGOLANG_API __declspec(dllimport)
  #endif
#elif __GNUC__ >= 4
    #define LIBGOLANG_API __attribute__ ((visibility ("default")))
#else
    #define LIBGOLANG_API
#endif


// ---- C-level API that is always available ----
// (most of the functions are documented in libgolang.cpp)

#ifdef  __cplusplus
namespace golang {
extern "C" {
#endif

#ifdef __cplusplus
    [[noreturn]]
#else
    _Noreturn
#endif
LIBGOLANG_API void panic(const char *arg);
LIBGOLANG_API const char *recover(void);

LIBGOLANG_API void _tasknanosleep(uint64_t dt);
LIBGOLANG_API uint64_t _nanotime(void);


// libgolang runtime - the runtime must be initialized before any other libgolang use.
typedef struct _libgolang_runtime_ops {
    // nanosleep should pause current goroutine for at least dt nanoseconds.
    // nanosleep(0) is not noop - such call must be at least yielding to other goroutines.
    void        (*nanosleep)(uint64_t dt);

    // nanotime should return current time since EPOCH in nanoseconds.
    uint64_t    (*nanotime)(void);

} _libgolang_runtime_ops;

LIBGOLANG_API void _libgolang_init(const _libgolang_runtime_ops *runtime_ops);


#ifdef __cplusplus
}}
#endif


// ---- C++-level API that is available when compiling with C++ ----

#ifdef __cplusplus

namespace golang {

namespace time {

// sleep pauses current goroutine for at least dt seconds.
LIBGOLANG_API void sleep(double dt);

// now returns current time in seconds.
LIBGOLANG_API double now();

}   // golang::time::

}   // golang::
#endif  // __cplusplus

#endif  // _NXD_LIBGOLANG_H
