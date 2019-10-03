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

typedef struct Point {
    int x, y;
} Point;

void _test_chan_c(void) {
    _chan *done = _makechan(0, 0);
    _chan *chi  = _makechan(sizeof(int), 1);
    _chan *chp  = NULL;

    int   i, j, _;
    Point p;
    bool  jok;

    i=+1; _chansend(chi, &i);
    j=-1; _chanrecv(chi, &j);
    if (j != i)
        panic("send -> recv != I");

    i = 2;
    _selcase sel[5];
    sel[0]  = _selrecv(done, NULL);
    sel[1]  = _selsend(chi, &i);
    sel[2]  = _selrecv(chp, &p);
    sel[3]  = _selrecv_(chi, &j, &jok);
    sel[4]  = _default;
    _ = _chanselect(sel, 5);
    if (_ != 1)
        panic("select: selected !1");

    jok = _chanrecv_(chi, &j);
    if (!(j == 2 && jok == true))
        panic("recv_ != (2, true)");

    _chanclose(chi);
    jok = _chanrecv_(chi, &j);
    if (!(j == 0 && jok == false))
        panic("recv_ from closed != (0, false)");

    _chanxdecref(done);
    _chanxdecref(chi);
    _chanxdecref(chp);
}

// small test to verify C _taskgo.
struct _work_arg{int i; _chan *done;};
static void _work(void *);
void _test_go_c(void) {
    _chan *done = _makechan(0,0);
    struct _work_arg *_ = malloc(sizeof(*_));
    if (_ == NULL)
        panic("malloc _work_arg -> failed");
    _->i    = 111;
    _->done = done;
    _taskgo(_work, _);
    _chanrecv(done, NULL);
    _chanxdecref(done);
}
static void _work(void *__) {
    struct _work_arg *_ = (struct _work_arg *)__;
    if (_->i != 111)
        panic("_work: i != 111");
    _chanclose(_->done);
    free(_);
}
