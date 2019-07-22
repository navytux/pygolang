#ifndef	_PYGOLANG_GOLANG_H
#define	_PYGOLANG_GOLANG_H

// Copyright (C) 2018-2019  Nexedi SA and Contributors.
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

// ---- C-level API that is always available ----

#ifdef	__cplusplus
extern "C" {
#endif

void panic(const char *arg);
const char *recover();
void bug(const char *arg);

struct _chan;
_chan *_makechan(unsigned elemsize, unsigned size);
void _chansend(_chan *ch, const void *ptx);
bool _chanrecv_(_chan *ch, void *prx);
void _chanrecv(_chan *ch, void *prx);
void _chanclose(_chan *ch);
unsigned _chanlen(_chan *ch);

// _selcase represents one _select case.
struct _selcase {
    _chan *ch;                      // channel
    void  *op;                      // chansend/chanrecv/chanrecv_/default
    void  *data;                    // chansend: ptx; chanrecv*: prx
    bool  *rxok;                    // chanrecv_: where to save ok; otherwise not used
};

int _chanselect(const _selcase *casev, int casec);

extern const _selcase _default; // XXX _seldefault ?
//void _default(_chan *, void *);

bool _tchanblocked(_chan *ch, bool recv, bool send);

#ifdef __cplusplus
}
#endif


// ---- C++-level API that is available when compiling with C++ ----

#ifdef __cplusplus

#include <exception>        // bad_alloc & co
#include <initializer_list>

// chan<T> provides type-safe wrapper over _chan.
template<typename T>
struct chan {
    _chan *_ch;

    // = nil channel if not initialized
    chan() { _ch = 0; }

    // XXX copy = ok?
    // XXX free on dtor? ref-count? (i.e. shared_ptr ?)

    // XXX send: `T *ptx` <-> `T tx` ?
    void send(T tx)             { _chansend(_ch, &tx);          }
    bool recv_(T *prx)          { return _chanrecv_(_ch, prx);  }
    void recv(T *prx)           { _chanrecv(_ch, prx);          }
    void close()                { _chanclose(_ch);              }
    unsigned len()              { return _chanlen(_ch);         }
};

template<typename T>
chan<T> makechan(unsigned size) {
    chan<T> ch;
    ch._ch = _makechan(sizeof(T), size);
    if (ch._ch == 0)
        throw std::bad_alloc();
    return ch;
}


// select, together with _send<T>, _recv<T>, _recv_<T> and _default, provide
// type-safe wrapper over _chanselect.
static inline
int select(const std::initializer_list<_selcase> &casev) {
    return _chanselect(casev.begin(), casev.size());
}

// _send<T> creates `ch<T>.send(tx)` case for select.
template<typename T>
_selcase _send(chan<T> ch, T tx) {  // XXX bad - taking address of temp tx -> &?
    return _selcase{
        .ch      = ch._ch,
        .op      = (void *)_chansend,
        .data    = &tx,
        .rxok    = NULL,
    };
}

// _recv<T> creates `ch<T>.recv(prx)` case for select.
template<typename T>
_selcase _recv(chan<T> ch, T *prx) {
    return _selcase{
        .ch      = ch._ch,
        .op      = (void *)_chanrecv,
        .data    = prx,
        .rxok    = NULL,
    };
}

// _recv_<T> creates `*pok = ch.recv_(prx)` case for select.
template<typename T>
_selcase _recv_(chan<T> ch, T *prx, bool *pok) {
    return _selcase{
        .ch     = ch._ch,
        .op     = (void *)_chanrecv_,
        .data   = prx,
        .rxok   = pok,
    };
}

// XXX _default

#endif  // __cplusplus

#endif  // _PYGOLANG_GOLANG_H
