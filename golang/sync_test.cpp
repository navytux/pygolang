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

#include "golang/sync.h"
#include "golang/_testing.h"
using namespace golang;

// verify that sync::Once works.
void _test_sync_once_cpp() {
    sync::Once once;
    int ncall = 0;
    ASSERT(ncall == 0);
    once.do_([&]() {
        ncall++;
    });
    ASSERT(ncall == 1);
    once.do_([&]() {
        ncall++;
    });
    ASSERT(ncall == 1);
    once.do_([&]() {
        ncall++;
        panic("should not panic");
    });
    ASSERT(ncall == 1);
}
