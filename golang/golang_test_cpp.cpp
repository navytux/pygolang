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

// Test that excersizes C++-level golang.h API.

#include "golang.h"
#include <stdio.h>
using namespace golang;

struct Point {
    int x, y;
};

void _test_chan_cpp() {
    chan<int>   chi = makechan<int>(1);
    chan<Point> chp = makechan<Point>(); chp = NULL;

    int   i, j;
    Point p;
    bool  jok;

    i=+1; chi.send(&i);
    j=-1; chi.recv(&j);
    if (!(j == i))
        panic("send -> recv != I");

    i = 2;
    int _ = select({
        _send(chi, &i),         // 0
        _recv(chp, &p),         // 1
        _recv_(chi, &j, &jok),  // 2
        _default,               // 3
    });


    if (_ == 0)
        printf("tx\n");
    if (_ == 1)
        printf("rx\n");
    if (_ == 2)
        printf("rx_\n");
    if (_ == 3)
        printf("default\n");
}
