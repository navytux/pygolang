#ifndef _NXD_LIBGOLANG_STRINGS_H
#define _NXD_LIBGOLANG_STRINGS_H

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

// Package strings mirrors Go package strings.
//
//  - `has_prefix` checks whether string starts from prefix.
//  - `has_suffix` checks whether string ends   with suffix.
//  - `trim_prefix` removes prefix from a string.
//  - `trim_suffix` removes suffix from a string.
//  - `split` splits string by delimiter.
//
// See also https://golang.org/pkg/strings for Go strings package documentation.

#include <golang/libgolang.h>
#include <vector>

// golang::strings::
namespace golang {
namespace strings {

// has_prefix checks whether string starts from prefix.
LIBGOLANG_API bool has_prefix(const string &s, const string &prefix);
LIBGOLANG_API bool has_prefix(const string &s, char prefix);

// has_suffix checks whether string ends   with suffix.
LIBGOLANG_API bool has_suffix(const string &s, const string &suffix);
LIBGOLANG_API bool has_suffix(const string &s, char suffix);

// trim_prefix removes prefix from string s.
//
// If s does not start from prefix, nothing is removed.
LIBGOLANG_API string trim_prefix(const string &s, const string &prefix);
LIBGOLANG_API string trim_prefix(const string &s, char prefix);

// trim_suffix removes suffix from string s.
//
// If s does not end with suffix, nothing is removed.
LIBGOLANG_API string trim_suffix(const string &s, const string &suffix);
LIBGOLANG_API string trim_suffix(const string &s, char suffix);

// split splits string s by separator sep.
//
// For example split("hello world zzz", ' ') -> ["hello", "world", "zzz"].
LIBGOLANG_API std::vector<string> split(const string &s, char sep);

}}  // golang::strings::


#endif  // _NXD_LIBGOLANG_STRINGS_H
