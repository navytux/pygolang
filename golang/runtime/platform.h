#ifndef _NXD_LIBGOLANG_RUNTIME_PLATFORM_H
#define _NXD_LIBGOLANG_RUNTIME_PLATFORM_H

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

// Header platform.h provides preprocessor defines that describe target platform.

// LIBGOLANG_OS_<X> is defined on operating system X.
//
// List of supported operating systems: linux, darwin, windows.
#ifdef __linux__
# define LIBGOLANG_OS_linux     1
#elif defined(__APPLE__)
# define LIBGOLANG_OS_darwin    1
#elif defined(_WIN32) || defined(__CYGWIN__)
# define LIBGOLANG_OS_windows   1
#else
# error "unsupported operating system"
#endif

// LIBGOLANG_CC_<X> is defined on C/C++ compiler X.
//
// List of supported compilers: gcc, clang, msc.
#ifdef __clang__
# define LIBGOLANG_CC_clang     1
#elif defined(_MSC_VER)
# define LIBGOLANG_CC_msc       1
// NOTE gcc comes last because e.g. clang and icc define __GNUC__ as well
#elif __GNUC__
# define LIBGOLANG_CC_gcc       1
#else
# error "unsupported compiler"
#endif

#endif  // _NXD_LIBGOLANG_RUNTIME_PLATFORM_H
