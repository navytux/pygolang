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

// Test that exercises C++-level libgolang.h API and functionality.

#include "golang/libgolang.h"
using namespace golang;

// small test to verify C++ go.
static void _work(int i);
void _test_go_cpp() {
    go(_work, 111); // not λ to test that go correctly passes arguments
    // TODO wait till _work is done
}
static void _work(int i) {
    if (i != 111)
        panic("_work: i != 111");
}
