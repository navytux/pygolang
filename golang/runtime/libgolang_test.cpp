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

// Test that exercises C++-level libgolang.h API and functionality.

#include "golang/libgolang.h"
#include "golang/time.h"

#include <stdio.h>
#include <tuple>
#include <utility>
#include <string.h>
#include <vector>

#include "golang/_testing.h"
using namespace golang;
using std::move;
using std::tie;
using std::vector;

// verify chan<T> automatic reference counting.
void _test_chan_cpp_refcount() {
    chan<int> ch;
    ASSERT(ch == nil);
    ASSERT(!(ch != nil));
    ASSERT(ch._rawchan() == nil);

    ch = makechan<int>();
    ASSERT(!(ch == nil));
    ASSERT(ch != nil);
    ASSERT(ch._rawchan() != nil);
    _chan *_ch = ch._rawchan();
    ASSERT(_chanrefcnt(_ch) == 1);

    // copy ctor
    {
        chan<int> ch2(ch);
        ASSERT(ch2._rawchan() == _ch);
        ASSERT(_chanrefcnt(_ch) == 2);
        ASSERT(ch2 == ch);
        ASSERT(!(ch2 != ch));
        // ch2 goes out of scope, decref'ing via ~chan
    }
    ASSERT(_chanrefcnt(_ch) == 1);

    // copy =
    {
        chan<int> ch2;
        ASSERT(ch2 == nil);
        ASSERT(ch2._rawchan() == nil);

        ch2 = ch;
        ASSERT(ch2._rawchan() == _ch);
        ASSERT(_chanrefcnt(_ch) == 2);
        ASSERT(ch2 == ch);
        ASSERT(!(ch2 != ch));

        ch2 = nil;
        ASSERT(ch2 == nil);
        ASSERT(ch2._rawchan() == nil);
        ASSERT(_chanrefcnt(_ch) == 1);
        ASSERT(!(ch2 == ch));
        ASSERT(ch2 != ch);
    }
    ASSERT(_chanrefcnt(_ch) == 1);

    // move ctor
    chan<int> ch2(move(ch));
    ASSERT(ch == nil);
    ASSERT(ch._rawchan() == nil);
    ASSERT(ch2 != nil);
    ASSERT(ch2._rawchan() == _ch);
    ASSERT(_chanrefcnt(_ch) == 1);

    // move =
    ch = move(ch2);
    ASSERT(ch != nil);
    ASSERT(ch._rawchan() == _ch);
    ASSERT(ch2 == nil);
    ASSERT(ch2._rawchan() == nil);
    ASSERT(_chanrefcnt(_ch) == 1);

    // ch goes out of scope and destroys raw channel
}


// verify chan<T> IO.
struct Point {
    int x, y;
};

void _test_chan_cpp() {
    chan<structZ> done = makechan<structZ>();
    chan<int>     chi  = makechan<int>(1);
    chan<Point>   chp  = makechan<Point>(); chp = nil;

    int   i, j, _;
    Point p;
    bool  jok;

    i=+1; chi.send(i);
    j=-1; j = chi.recv();
    if (j != i)
        panic("send -> recv != I");

    i = 2;
    _ = select({
        done.recvs(),           // 0
        chi.sends(&i),          // 1
        chp.recvs(&p),          // 2
        chi.recvs(&j, &jok),    // 3
        _default,               // 4
    });
    if (_ != 1)
        panic("select: selected !1");

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

// waitBlocked waits until at least nrx recv and ntx send operations block
// waiting on the channel.
void waitBlocked(_chan *ch, int nrx, int ntx) {
    if (ch == nil)
        panic("wait blocked: called on nil channel");

    double t0 = time::now();
    while (1) {
        if ((_tchanrecvqlen(ch) >= nrx) && (_tchansendqlen(ch) >= ntx))
            return;

        double now = time::now();
        if (now-t0 > 10) // waited > 10 seconds - likely deadlock
            panic("deadlock");
        time::sleep(0);  // yield to another thread / coroutine
    }
}

template<typename T> void waitBlocked_RX(chan<T> ch) {
    waitBlocked(ch._rawchan(), /*nrx=*/1, /*ntx=*/0);
}
template<typename T> void waitBlocked_TX(chan<T> ch) {
    waitBlocked(ch._rawchan(), /*nrx=*/0, /*ntx=*/1);
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
static void usestack_and_call(func<void()> f, int nframes=128) {
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
    go([ch]() {
        waitBlocked_RX(ch);
        usestack_and_call([ch]() {
            ch.send(111);
        });
    });
    usestack_and_call([ch]() {
        int rx = ch.recv();
        if (rx != 111)
            panic("recv(111) != 111");
    });

    // send
    auto done = makechan<structZ>();
    go([ch, done]() {
        waitBlocked_TX(ch);
        usestack_and_call([ch]() {
            int rx = ch.recv();
            if (rx != 222)
                panic("recv(222) != 222");
        });
        done.close();
    });
    usestack_and_call([ch]() {
        ch.send(222);
    });
    done.recv();

    // select(recv)
    go([ch]() {
        waitBlocked_RX(ch);
        usestack_and_call([ch]() {
            ch.send(333);
        });
    });
    usestack_and_call([ch]() {
        int rx = 0;
        int _ = select({ch.recvs(&rx)});
        if (_ != 0)
            panic("select(recv, 333): selected !0");
        if (rx != 333)
            panic("select(recv, 333): recv != 333");
    });

    // select(send)
    done = makechan<structZ>();
    go([ch, done]() {
        waitBlocked_TX(ch);
        usestack_and_call([ch]() {
            int rx = ch.recv();
            if (rx != 444)
                panic("recv(444) != 444");
        });
        done.close();
    });
    usestack_and_call([ch]() {
        int tx = 444;
        int _ = select({ch.sends(&tx)});
        if (_ != 0)
            panic("select(send, 444): selected !0");
    });
    done.recv();
}

// small test to verify C++ go.
static void _work(int i, chan<structZ> done);
void _test_go_cpp() {
    auto done = makechan<structZ>();
    go(_work, 111, done); // not λ to test that go correctly passes arguments
    done.recv();
}
static void _work(int i, chan<structZ> done) {
    if (i != 111)
        panic("_work: i != 111");
    done.close();
}

// verify that chan close wakes up all consumers atomically - in other words
// that it is safe to e.g. destroy the channel after recv wakeup caused by close.
//
// this also verifies that recv and select, upon wakeup, do not use channel
// object when it could be already destroyed.
void __test_close_wakeup_all(bool vs_select) {
    int i, N = 100;
    auto ch   = makechan<int>();
    auto _ch  = ch._rawchan();
    auto done = makechan<structZ>();

    // ch.recv subscriber that destroys ch right after wakeup.
    // ch ownership is transferred to this goroutine.
    go([ch, done, vs_select]() mutable {
        ch.recv();
        // destroy ch _before_ signalling on done. This should be safe to do
        // as other workers vvv don't use ch after wakeup from ch.recv().
        if (!vs_select)
            ASSERT(_chanrefcnt(ch._rawchan()) == 1);
        ch = nil;
        done.send(structZ{});
    });
    waitBlocked(_ch, /*nrx=*/1, /*ntx=*/0);
    ASSERT(_chanrefcnt(_ch) == 2);
    ch = nil;
    ASSERT(_chanrefcnt(_ch) == 1);

    // many other ch.recv or select({ch.recv}) subscribers queued to ch.recvq
    // their lifetime is subset of ^^^ subscriber lifetime; they don't own a ch reference.
    for (i=0; i < N; i++) {
        go([_ch, done, vs_select]() {
            if (!vs_select) {
                _chanrecv(_ch, nil);
            } else {
                int rx;
                select({
                    _selrecv(_ch, &rx)
                });
            }
            done.send(structZ{});
        });
    }

    // wait till all workers block in ch.recv()
    waitBlocked(_ch, /*nrx=*/1+N, 0);

    // ch.close() must wake up all workers atomically. If it is not the case,
    // this will reliably (N >> 1) trigger assert in chan decref on len(ch.recvq) == 0.
    ASSERT(_chanrefcnt(_ch) == (vs_select ? 1+N : 1));
    _chanclose(_ch);

    // wait till all workers finish
    for (i=0; i < 1+N; i++)
        done.recv();
}
void _test_close_wakeup_all_vsrecv()   { __test_close_wakeup_all(/*vs_select=*/false); }
void _test_close_wakeup_all_vsselect() { __test_close_wakeup_all(/*vs_select=*/true);  }

// verify that select correctly handles situation where a case that is already
// queued wins while select queues other cases.
void __test_select_win_while_queue() {
    const int Ncase =        1000; // many select cases to ↑ p(win-while-queue)
    const int Ndata = 1*1024*1024; // big element size to  ↑ time when case won, but not yet woken up
    int i;

    // Data is workaround for "error: function returning an array" if we use
    // chan<char[Ndata]> directly.
    struct Data { char _[Ndata]; };
    auto ch   = makechan<Data>();
    auto ch2  = makechan<int>();
    auto done = makechan<structZ>();

    Data *data_send = (Data *)calloc(1, sizeof(Data));
    Data *data_recv = (Data *)calloc(1, sizeof(Data));
    if (data_send == nil || data_recv == nil)
        throw std::bad_alloc();
    for (i=0; i<Ndata; i++)
        data_send->_[i] = i % 0xff;

    // win first select case (see vvv) right after it is queued.
    go([ch, data_send, done]() {
        waitBlocked_RX(ch);
        // select queued ch.recv and is likely still queing other cases.
        // -> win ch.recv
        ch.send(*data_send);
        done.close();
    });

    // select {ch.recv, ch2.recv, ch2.recv, ch2.recv, ...}
    _selcase casev[1+Ncase];
    bool ok=false;
    casev[0] = ch.recvs(data_recv, &ok);
    for (i=0; i<Ncase; i++)
        casev[1+i] = ch2.recvs();

    int _ = select(casev);
    ASSERT(_ == 0);
    ASSERT(ok == true);
    ASSERT(!memcmp(data_recv, data_send, sizeof(Data)));

    done.recv();
    free(data_send);
    free(data_recv);
}
void _test_select_win_while_queue() {
    int i, N = 100;
    for (i=0; i<N; i++)
        __test_select_win_while_queue();
}

// verify select behaviour with _INPLACE_DATA cases.
void _test_select_inplace() {
    auto ch = makechan<int>();
    int i;

    // inplace tx
    go([ch]() {
        _selcase sel[1];
        sel[0] = ch.sends(nil);
        *(int *)&sel[0].itxrx = 12345;
        sel[0].flags = _INPLACE_DATA;
        int _ = select(sel);
        ASSERT(_ == 0);
    });

    i = ch.recv();
    ASSERT(i == 12345);

    // inplace rx - currently forbidden to keep casev const.
    _selcase sel[1];
    sel[0] = ch.recvs();
    sel[0].flags = _INPLACE_DATA;
    const char *err = nil;
    try {
        select(sel);
    } catch (...) {
        err = recover();
    }
    ASSERT(err != nil);
    ASSERT(!strcmp(err, "select: recv into inplace data"));

    // _selcase ptx/prx
    _selcase cas = _default;

    err = nil;
    try {
        cas.ptx();
    } catch (...) {
        err = recover();
    }
    ASSERT(err != nil);
    ASSERT(!strcmp(err, "_selcase: ptx: op != send"));

    err = nil;
    try {
        cas.prx();
    } catch (...) {
        err = recover();
    }
    ASSERT(err != nil);
    ASSERT(!strcmp(err, "_selcase: prx: op != recv"));

    cas = ch.sends(&i);
    ASSERT(cas.ptx() == &i);
    cas.flags = _INPLACE_DATA;
    ASSERT(cas.ptx() == &cas.itxrx);

    cas = ch.recvs(&i);
    ASSERT(cas.prx() == &i);
    cas.flags = _INPLACE_DATA;
    err = nil;
    try {
        cas.prx();
    } catch (...) {
        err = recover();
    }
    ASSERT(err != nil);
    ASSERT(!strcmp(err, "_selcase: prx: recv with inplace data"));
}


// verify that defer works.
void __test_defer(vector<int> *pcalled) {
    defer([&]() {
        pcalled->push_back(1);
    });
    defer([&]() {
        pcalled->push_back(2);
    });
    return;
}
void _test_defer() {
    vector<int> called, ok({2, 1});
    __test_defer(&called);
    ASSERT(called == ok);
}


// verify refptr/object
class MyObj : public object {
public:
    void decref() {
        if (__decref())
            delete this;
    }

    int i;
    int myfunc(int j) { return i + j; }
};

void _test_refptr() {
    refptr<MyObj> p;
    ASSERT(p == nil);
    ASSERT(!(p != nil));
    ASSERT(p._ptr() == nil);

    MyObj *obj = new MyObj();
    ASSERT(obj->refcnt() == 1);
    obj->i = 3;

    // adoptref
    p = adoptref(obj);
    ASSERT(obj->refcnt() == 1);
    ASSERT(p._ptr() == obj);
    ASSERT(p->i == 3);              // ->
    ASSERT(p->myfunc(4) == 7);
    p->i = 2;
    ASSERT(obj->i == 2);
    ASSERT((*p).i == 2);            // *
    ASSERT((*p).myfunc(3) == 5);
    (*p).i = 3;
    ASSERT(obj->i == 3);

    // newref
    {
        refptr<MyObj> q = newref(obj);
        ASSERT(obj->refcnt() == 2);
        ASSERT(p._ptr() == obj);
        ASSERT(q._ptr() == obj);
        ASSERT(q->i == 3);
        obj->i = 4;
        ASSERT(q->i == 4);

        // q goes out of scope - obj decref'ed
    }
    ASSERT(obj->refcnt() == 1);

    // copy ctor
    {
        refptr<MyObj> q(p);
        ASSERT(obj->refcnt() == 2);
        ASSERT(p._ptr() == obj);
        ASSERT(q._ptr() == obj);
        ASSERT(p == q);
        // q goes out of scope - obj decref'ed
    }
    ASSERT(obj->refcnt() == 1);

    // copy =
    {
        refptr<MyObj> q;
        ASSERT(obj->refcnt() == 1);
        ASSERT(q == nil);
        ASSERT(q._ptr() == nil);
        ASSERT(!(p == q));
        ASSERT(p != q);

        q = p;
        ASSERT(obj->refcnt() == 2);
        ASSERT(p._ptr() == obj);
        ASSERT(q._ptr() == obj);
        ASSERT(p == q);
        ASSERT(!(p != q));

        q = nil;
        ASSERT(obj->refcnt() == 1);
        ASSERT(p._ptr() == obj);
        ASSERT(q._ptr() == nil);
        ASSERT(!(p == q));
        ASSERT(p != q);
    }
    ASSERT(obj->refcnt() == 1);

    // move ctor
    refptr<MyObj> q(move(p));
    ASSERT(obj->refcnt() == 1);
    ASSERT(p == nil);
    ASSERT(p._ptr() == nil);
    ASSERT(q != nil);
    ASSERT(q._ptr() == obj);

    // move =
    p = move(q);
    ASSERT(obj->refcnt() == 1);
    ASSERT(p != nil);
    ASSERT(p._ptr() == obj);
    ASSERT(q == nil);
    ASSERT(q._ptr() == nil);

    // p goes out of scope and destroys obj
}

void _test_global() {
    global<refptr<MyObj>> g;
    ASSERT(g == nil);
    ASSERT(!(g != nil));
    ASSERT(g._ptr() == nil);

    MyObj *obj = new MyObj();
    refptr<MyObj> p = adoptref(obj);
    ASSERT(obj->refcnt() == 1);
    obj->i = 3;

    ASSERT(g._ptr() == nil);
    ASSERT(p._ptr() == obj);
    ASSERT(!(g == p));
    ASSERT(!(p == g));
    ASSERT(g != p);
    ASSERT(p != g);

    // copy =       global <- refptr
    g = p;
    ASSERT(obj->refcnt() == 2);
    ASSERT(g._ptr() == obj);
    ASSERT(p._ptr() == obj);
    ASSERT(!(g == nil));
    ASSERT(g != nil);
    ASSERT(g == p);
    ASSERT(p == g);
    ASSERT(!(g != p));
    ASSERT(!(p != g));

    ASSERT(g->i == 3);      // ->
    g->i = 4;
    ASSERT(obj->i == 4);
    ASSERT((*g).i == 4);    // *
    (*g).i = 3;
    ASSERT(obj->i == 3);

    // global = nil     - obj reference is released
    ASSERT(obj->refcnt() == 2);
    g = nil;
    ASSERT(obj->refcnt() == 1);
    ASSERT(g._ptr() == nil);

    // copy ctor    global <- refptr
    {
        global<refptr<MyObj>> h(p);
        ASSERT(obj->refcnt() == 2);
        ASSERT(g._ptr() == nil);
        ASSERT(h._ptr() == obj);
        ASSERT(p._ptr() == obj);
        ASSERT(!(h == g));
        ASSERT(!(g == h));
        ASSERT(h == p);
        ASSERT(p == h);
        ASSERT(h != g);
        ASSERT(g != h);
        ASSERT(!(h != p));
        ASSERT(!(p != h));

        // h goes out of scope, but obj reference is _not_ released
    }
    ASSERT(obj->refcnt() == 2); // NOTE _not_ 1

    // reinit g again
    g = p;
    ASSERT(obj->refcnt() == 3);
    ASSERT(g._ptr() == obj);
    ASSERT(p._ptr() == obj);


    // copy ctor    refptr <- global
    {
        refptr<MyObj> q(g);
        ASSERT(obj->refcnt() == 4);
        ASSERT(g._ptr() == obj);
        ASSERT(p._ptr() == obj);
        ASSERT(q._ptr() == obj);
        // q goes out of scope - obj decref'ed
    }
    ASSERT(obj->refcnt() == 3);

    // copy =       refptr <- global
    {
        refptr<MyObj> q;
        q = g;
        ASSERT(obj->refcnt() == 4);
        ASSERT(g._ptr() == obj);
        ASSERT(p._ptr() == obj);
        ASSERT(q._ptr() == obj);
        // q goes out of scope - obj decref'ed
    }
    ASSERT(obj->refcnt() == 3);
}
