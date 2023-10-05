#ifndef _NXD_LIBGOLANG_RUNTIME_H
#define _NXD_LIBGOLANG_RUNTIME_H

// Copyright (C) 2023  Nexedi SA and Contributors.
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

// Package runtime mirrors Go package runtime.

#include "golang/libgolang.h"


// golang::runtime::
namespace golang {
namespace runtime {

// ARCH indicates processor architecture, that is running the program.
//
// e.g. "386", "amd64", "arm64", ...
extern LIBGOLANG_API const string ARCH;

// OS indicates operating system, that is running the program.
//
// e.g. "linux", "darwin", "windows", ...
extern LIBGOLANG_API const string OS;

// CC indicates C/C++ compiler, that compiled the program.
//
// e.g. "gcc", "clang", "msc", ...
extern LIBGOLANG_API const string CC;


}} // golang::runtime::

#endif  // _NXD_LIBGOLANG_RUNTIME_H
