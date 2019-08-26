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

// Test that exercises C-level libgolang.h API.

#ifdef __cplusplus
# error "this file must be compiled with C - not C++ - compiler"
#endif

#include "golang/libgolang.h"
#include <stdlib.h>

// small test to verify C _taskgo.
struct _work_arg{int i;};
static void _work(void *);
void _test_go_c(void) {
    struct _work_arg *_ = malloc(sizeof(*_));
    if (_ == NULL)
        panic("malloc _work_arg -> failed");
    _->i    = 111;
    _taskgo(_work, _);
    // TODO wait till _work is done
}
static void _work(void *__) {
    struct _work_arg *_ = (struct _work_arg *)__;
    if (_->i != 111)
        panic("_work: i != 111");
    free(_);
}
