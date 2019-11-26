#ifndef _NXD_LIBGOLANG_FMT_H
#define _NXD_LIBGOLANG_FMT_H

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

// Package fmt mirrors Go package fmt.
//
//  - `sprintf` formats text into string.
//  - `errorf`  formats text into error.
//
// NOTE: formatting rules are those of libc, not Go.
//
// See also https://golang.org/pkg/fmt for Go fmt package documentation.

#include <golang/libgolang.h>

// golang::fmt::
namespace golang {
namespace fmt {

// sprintf formats text into string.
LIBGOLANG_API string sprintf(const string &format, ...);

// `errorf`  formats text into error.
LIBGOLANG_API error  errorf (const string &format, ...);

// `const char *` overloads just to catch format mistakes as
// __attribute__(format) does not work with std::string.
LIBGOLANG_API string sprintf(const char *format, ...)
                                __attribute__ ((format (printf, 1, 2)));
LIBGOLANG_API error  errorf (const char *format, ...)
                                __attribute__ ((format (printf, 1, 2)));

}}  // golang::fmt::

#endif  // _NXD_LIBGOLANG_FMT_H
