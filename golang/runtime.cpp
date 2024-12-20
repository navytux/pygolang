// Copyright (C) 2023-2024  Nexedi SA and Contributors.
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

// Package runtime mirrors Go package runtime.
// See runtime.h for package overview.

#include "golang/runtime.h"


// golang::runtime::
namespace golang {
namespace runtime {

const string OS =
#ifdef LIBGOLANG_OS_linux
    "linux"
#elif defined(LIBGOLANG_OS_darwin)
    "darwin"
#elif defined(LIBGOLANG_OS_windows)
    "windows"
#else
# error
#endif
    ;


const string CC =
#ifdef LIBGOLANG_CC_gcc
    "gcc"
#elif defined(LIBGOLANG_CC_clang)
    "clang"
#elif defined(LIBGOLANG_CC_msc)
    "msc"
#else
# error
#endif
    ;


}}  // golang::runtime::
