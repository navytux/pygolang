#ifndef _NXD_LIBGOLANG_UNICODE_UTF8_H
#define _NXD_LIBGOLANG_UNICODE_UTF8_H

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

// Package utf8 mirrors Go package utf8.

#include <golang/libgolang.h>

// golang::unicode::utf8::
namespace golang {
namespace unicode {
namespace utf8 {

constexpr rune RuneError = 0xFFFD;  // unicode replacement character

}}} // golang::os::utf8::

#endif  // _NXD_LIBGOLANG_UNICODE_UTF8_H
