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

// Test that excersizes C++-level libgolang.h API and functionality.

#include "golang/libgolang.h"
#include <stdio.h>
#include <tuple>
using namespace golang;
using std::function;
using std::tie;


struct Point {
    int x, y;
};

void _test_chan_cpp() {
    chan<int>   chi = makechan<int>(1);
    chan<Point> chp = makechan<Point>(); chp = NULL;

    int   i, j, _;
    Point p;
    bool  jok;

    i=+1; chi.send(i);
    j=-1; j = chi.recv();
    if (j != i)
        panic("send -> recv != I");

    i = 2;
    _ = select({
        _send(chi, &i),         // 0
        _recv(chp, &p),         // 1
        _recv_(chi, &j, &jok),  // 2
        _default,               // 3
    });
    if (_ != 0)
        panic("select: selected !0");

    tie(j, jok) = chi.recv_();
    if (!(j == 2 && jok == true))
        panic("recv_ != (2, true)");

    chi.close();
    tie(j, jok) = chi.recv_();
    if (!(j == 0 && jok == false))
        panic("recv_ from closed != (0, false)");

    // XXX chan<chan> is currently TODO
    //chan<chan<int>> zzz;
}

// waitBlocked waits until either a receive (if rx) or send (if tx) operation
// blocks waiting on the channel.
void waitBlocked(_chan *ch, bool rx, bool tx) {
//  printf("wait blocked %p  rx=%d  tx=%d\n", ch, rx, tx);
    if (ch == NULL)
        panic("wait blocked: called on nil channel");

    double t0 = time::now();
    while (1) {
//      printf("\t%p  len(rxq): %d  len(txq): %d\n", ch, _tchanrecvqlen(ch), _tchansendqlen(ch));
        if (rx && (_tchanrecvqlen(ch) != 0))
            return;
        if (tx && (_tchansendqlen(ch) != 0))
            return;

        double now = time::now();
        if (now-t0 > 10) // waited > 10 seconds - likely deadlock
            panic("deadlock");
        time::sleep(0);  // yield to another thread / coroutine
    }
}

template<typename T> void waitBlocked_RX(chan<T> ch) {
    waitBlocked(ch._rawchan(), /*rx=*/true, /*tx=*/0);
}
template<typename T> void waitBlocked_TX(chan<T> ch) {
    waitBlocked(ch._rawchan(), /*rx=*/0, /*tx=*/true);
}

// usestack_and_call pushes C-stack down and calls f from that.
// C-stack pushdown is used to make sure that when f will block and switched
// to another g, greenlet will save f's C-stack frame onto heap.
//
//   ---  ~~~
//             stack of another g
//   ---  ~~~
//
//    .
//    .
//    .
//
//    f    ->  heap
static void usestack_and_call(function<void()> f, int nframes=128) {
    if (nframes == 0) {
        f();
        return;
    }
    return usestack_and_call(f, nframes-1);
}

// verify that send/recv/select correctly route their onstack arguments through onheap proxies.
void _test_chan_vs_stackdeadwhileparked() {
    // problem: under greenlet g's stack lives on system stack and is swapped as needed
    // onto heap and back on g switch. This way if e.g. recv() is called with
    // prx pointing to stack, and the stack is later copied to heap and replaced
    // with stack of another g, the sender, if writing to original prx directly,
    // will write to stack of different g, and original recv g, after wakeup,
    // will see unchanged memory - with stack content that was saved to heap.
    //
    // to avoid this, send/recv/select create onheap proxies for onstack
    // arguments and use those proxies as actual argument for send/receive.

    // recv
    auto ch = makechan<int>();
    go([&]() {
        waitBlocked_RX(ch);
        usestack_and_call([&]() {
            //int tx = 111; ch.send(&tx);
            ch.send(111);
        });
    });
    usestack_and_call([&]() {
        //int rx; ch.recv(&rx);
        int rx = ch.recv();
        if (rx != 111)
            panic("recv(111) != 111");
    });

    // send
    auto done = makechan<structZ>();
    go([&]() {
        waitBlocked_TX(ch);
        usestack_and_call([&]() {
            //int rx = 0; ch.recv(&rx);
            int rx = ch.recv();
            if (rx != 222)
                panic("recv(222) != 222");
        });
        done.close();
    });
    usestack_and_call([&]() {
        //int tx = 222; ch.send(&tx);
        ch.send(222);
    });
    //done.recv(NULL);
    done.recv();

    // select(recv)
    go([&]() {
        waitBlocked_RX(ch);
        usestack_and_call([&]() {
            //int tx = 333; ch.send(&tx);
            ch.send(333);
        });
    });
    usestack_and_call([&]() {
        int rx = 0;
        int _ = select({_recv(ch, &rx)});
        if (_ != 0)
            panic("select(recv, 333): selected !0");
//      printf("\n\nrx: %d\n", rx);
        if (rx != 333)
            panic("select(recv, 333): recv != 333");
    });

    // select(send)
    done = makechan<structZ>();
    go([&]() {
        waitBlocked_TX(ch);
        usestack_and_call([&]() {
            //int rx = 0; ch.recv(&rx);
            int rx = ch.recv();
//          printf("RX: %d\n", rx);
            if (rx != 444)
                panic("recv(444) != 444");
        });
        done.close();
    });
    usestack_and_call([&]() {
        int tx = 444;
        int _ = select({_send(ch, &tx)});
        if (_ != 0)
            panic("select(send, 444): selected !0");
    });
    //done.recv(NULL);
    done.recv();
}
