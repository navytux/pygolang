#ifndef _NXD_LIBGOLANG_IO_H
#define _NXD_LIBGOLANG_IO_H

// Copyright (C) 2019-2020  Nexedi SA and Contributors.
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

// Package io mirrors Go package io.

#include <golang/libgolang.h>

// golang::io::
namespace golang {
namespace io {

// EOF_ is the error that indicates that e.g. read reached end of file or stream.
//
// Note: the name is EOF_, not EOF, to avoid conflict with EOF define by stdio.h.
extern LIBGOLANG_API const global<error> EOF_;

// ErrUnexpectedEOF is the error that indicates that EOF was reached, but was not expected.
extern LIBGOLANG_API const global<error> ErrUnexpectedEOF;

}}  // golang::io::

#endif	// _NXD_LIBGOLANG_IO_H
