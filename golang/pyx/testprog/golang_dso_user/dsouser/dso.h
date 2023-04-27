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

#ifndef _NXD_GOLANG_DSOUSER_DSO_H
#define _NXD_GOLANG_DSOUSER_DSO_H

#include <golang/libgolang.h>

#if BUILDING_DSOUSER_DSO
#  define DSOUSER_DSO_API LIBGOLANG_DSO_EXPORT
#else
#  define DSOUSER_DSO_API LIBGOLANG_DSO_IMPORT
#endif

DSOUSER_DSO_API void dsotest();

#endif // _NXD_GOLANG_DSOUSER_DSO_H
