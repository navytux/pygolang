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

#include <stddef.h>

// ---- C-level API that is always available ----

#ifdef	__cplusplus
extern "C" {
#endif

void panic(const char *arg);
const char *recover();

struct _chan;
_chan *_makechan(unsigned elemsize, unsigned size);
void _chansend(_chan *ch, const void *ptx);
bool _chanrecv_(_chan *ch, void *prx);
void _chanrecv(_chan *ch, void *prx);
void _chanclose(_chan *ch);
unsigned _chanlen(_chan *ch);

enum _chanop {
    _CHANSEND   = 0,
    _CHANRECV   = 1,
    _CHANRECV_  = 2,
    _DEFAULT    = 3,
};

// _selcase represents one _select case.
struct _selcase {
    _chan           *ch;    // channel
    enum _chanop    op;     // chansend/chanrecv/chanrecv_/default
    void            *data;  // chansend: ptx; chanrecv*: prx
    bool            *rxok;  // chanrecv_: where to save ok; otherwise not used
};

int _chanselect(const _selcase *casev, int casec);

// _selsend creates `_chansend(ch, ptx)` case for _chanselect.
static inline
struct _selcase _selsend(struct _chan *ch, const void *ptx) {
    struct _selcase _{
        .ch     = ch,
        .op      = _CHANSEND,
        .data    = (void *)ptx,
        .rxok    = NULL,
    };
    return _;
}

// _selrecv creates `_chanrecv(ch, prx)` case for _chanselect.
static inline
struct _selcase _selrecv(struct _chan *ch, void *prx) {
    struct _selcase _{
        .ch     = ch,
        .op      = _CHANRECV,
        .data    = prx,
        .rxok    = NULL,
    };
    return _;
}

// _selrecv_ creates `*pok = _chanrecv_(ch, prx)` case for _chanselect.
static inline
struct _selcase _selrecv_(struct _chan *ch, void *prx, bool *pok) {
    struct _selcase _{
        .ch     = ch,
        .op      = _CHANRECV_,
        .data    = prx,
        .rxok    = pok,
    };
    return _;
}

// _default represents default case for _select.
extern const _selcase _default;

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
    chan() { _ch = NULL; }

    // XXX copy = ok?
    // XXX free on dtor? ref-count? (i.e. shared_ptr ?)

    // XXX send & in general bad - e.g. if tx was auto-created temporary - must be `T *ptx`
    // ( for single send & could be ok, but for select, where _send returns and
    //   then select runs - not ok )
    void send(const T *ptx)     { _chansend(_ch, ptx);          }
    bool recv_(T *prx)          { return _chanrecv_(_ch, prx);  }
    void recv(T *prx)           { _chanrecv(_ch, prx);          }
    void close()                { _chanclose(_ch);              }
    unsigned len()              { return _chanlen(_ch);         }
};

template<typename T>
chan<T> makechan(unsigned size) {
    chan<T> ch;
    ch._ch = _makechan(sizeof(T), size);
    if (ch._ch == NULL)
        throw std::bad_alloc();
    return ch;
}


// select, together with _send<T>, _recv<T> and _recv_<T>, provide type-safe
// wrappers over _chanselect and _selsend/_selrecv/_selrecv_.
static inline
int select(const std::initializer_list<_selcase> &casev) {
    return _chanselect(casev.begin(), casev.size());
}

// _send<T> creates `ch<T>.send(ptx)` case for select.
template<typename T>
_selcase _send(chan<T> ch, const T *ptx) {
    return _selsend(ch._ch, ptx);
}

// _recv<T> creates `ch<T>.recv(prx)` case for select.
template<typename T>
_selcase _recv(chan<T> ch, T *prx) {
    return _selrecv(ch._ch, prx);
}

// _recv_<T> creates `*pok = ch.recv_(prx)` case for select.
template<typename T>
_selcase _recv_(chan<T> ch, T *prx, bool *pok) {
    return _selrecv_(ch._ch, prx, pok);
}

#endif  // __cplusplus

#endif  // _PYGOLANG_GOLANG_H
