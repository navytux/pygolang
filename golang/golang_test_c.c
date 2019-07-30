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

// Test that excersizes C-level golang.h API.

#ifdef __cplusplus
# error "this file must be compiled with C - not C++ - compiler"
#endif

#include "golang.h"
#include <stdio.h>

// XXX -> common place
#ifndef ARRAY_SIZE
# define ARRAY_SIZE(A) (sizeof(A) / sizeof((A)[0]))
#endif

void test_chan_c(void) {
    _chan *a = NULL, *b = NULL;
    int tx = 1, arx; bool aok;
    int rx;

    _selcase sel[4];
    sel[0]  = _selsend(a, &tx);
    sel[1]  = _selrecv(b, &rx);
    sel[2]  = _selrecv_(a, &arx, &aok);
    sel[3]  = _default;
    int _ = _chanselect(sel, ARRAY_SIZE(sel));

    if (_ == 0)
        printf("tx\n");
    if (_ == 1)
        printf("rx\n");
    if (_ == 2)
        printf("rx_\n");
    if (_ == 3)
        printf("defaut\n");
}
