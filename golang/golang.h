#ifndef _PYGOLANG_GOLANG_H
#define _PYGOLANG_GOLANG_H

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
#include <stdbool.h>

// ---- C-level API that is always available ----

#ifdef  __cplusplus
namespace golang {
extern "C" {
#endif

#ifdef __cplusplus
    [[noreturn]]
#else
    _Noreturn
#endif
void panic(const char *arg);
const char *recover(void);

typedef struct _chan _chan;
_chan *_makechan(unsigned elemsize, unsigned size);
void _chanxincref(_chan *ch);
void _chanxdecref(_chan *ch);
void _chansend(_chan *ch, const void *ptx);
void _chanrecv(_chan *ch, void *prx);
bool _chanrecv_(_chan *ch, void *prx);
void _chanclose(_chan *ch);
unsigned _chanlen(_chan *ch);
unsigned _chancap(_chan *ch);

enum _chanop {
    _CHANSEND   = 0,
    _CHANRECV   = 1,
    _CHANRECV_  = 2,
    _DEFAULT    = 3,
};

// _selcase represents one _select case.
typedef struct _selcase {
    _chan           *ch;    // channel
    enum _chanop    op;     // chansend/chanrecv/chanrecv_/default
    void            *data;  // chansend: ptx; chanrecv*: prx
    bool            *rxok;  // chanrecv_: where to save ok; otherwise not used
} _selcase;

int _chanselect(const _selcase *casev, int casec);

// _selsend creates `_chansend(ch, ptx)` case for _chanselect.
static inline
_selcase _selsend(_chan *ch, const void *ptx) {
    _selcase _ = {
        .ch     = ch,
        .op     = _CHANSEND,
        .data   = (void *)ptx,
        .rxok   = NULL,
    };
    return _;
}

// _selrecv creates `_chanrecv(ch, prx)` case for _chanselect.
static inline
_selcase _selrecv(_chan *ch, void *prx) {
    _selcase _ = {
        .ch     = ch,
        .op     = _CHANRECV,
        .data   = prx,
        .rxok   = NULL,
    };
    return _;
}

// _selrecv_ creates `*pok = _chanrecv_(ch, prx)` case for _chanselect.
static inline
_selcase _selrecv_(_chan *ch, void *prx, bool *pok) {
    _selcase _ = {
        .ch     = ch,
        .op     = _CHANRECV_,
        .data   = prx,
        .rxok   = pok,
    };
    return _;
}

// _default represents default case for _select.
extern const _selcase _default;

// for testing
int _tchanrecvqlen(_chan *ch);
int _tchansendqlen(_chan *ch);
extern void (*_tblockforever)(void);

#ifdef __cplusplus
}}
#endif


// ---- C++-level API that is available when compiling with C++ ----

#ifdef __cplusplus

#include <exception>        // bad_alloc & co
#include <initializer_list>

namespace golang {

template<typename T> class chan;
template<typename T> chan<T> makechan(unsigned size=0);
template<typename T> _selcase _send(chan<T>, const T*);
template<typename T> _selcase _recv(chan<T>, T*);
template<typename T> _selcase _recv_(chan<T>, T*, bool*);

// chan<T> provides type-safe wrapper over _chan.
template<typename T>
class chan {
    _chan *_ch;

public:
    chan() { _ch = NULL; } // nil channel if not initialized
    friend chan<T> makechan<T>(unsigned size);
    ~chan() { _chanxdecref(_ch); _ch = NULL; }

    // = nil
    chan(nullptr_t) { _ch = NULL; }
    chan& operator=(nullptr_t) { _chanxdecref(_ch); _ch = NULL; return *this; }
    // copy
    chan(const chan& from) { _ch = from._ch; _chanxincref(_ch); }
    chan& operator=(const chan& from) {
        if (this != &from) {
            _chanxdecref(_ch); _ch = from._ch; _chanxincref(_ch);
        }
        return *this;
    }
    // move
    chan(chan&& from) { _ch = from._ch; from._ch = NULL; }
    chan& operator=(chan&& from) {
        if (this != &from) {
            _chanxdecref(_ch); _ch = from._ch; from._ch = NULL;
        }
        return *this;
    }

    void send(const T *ptx)     { _chansend(_ch, ptx);          }
    void recv(T *prx)           { _chanrecv(_ch, prx);          }
    bool recv_(T *prx)          { return _chanrecv_(_ch, prx);  }
    void close()                { _chanclose(_ch);              }
    unsigned len()              { return _chanlen(_ch);         }
    unsigned cap()              { return _chancap(_ch);         }

    bool operator==(nullptr_t)  { return (_ch == NULL); }
    bool operator!=(nullptr_t)  { return (_ch != NULL); }

    // for testing
    _chan *_rawchan()           { return _ch;   }

    friend _selcase _send<T>(chan<T>, const T*);
    friend _selcase _recv<T>(chan<T>, T*);
    friend _selcase _recv_<T>(chan<T>, T*, bool*);
};

// makechan<T> makes new chan<T> with capacity=size.
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
static inline                       // select({case1, case2, case3})
int select(const std::initializer_list<const _selcase> &casev) {
    return _chanselect(casev.begin(), casev.size());
}

template<size_t N> static inline    // select(casev_array)
int select(const _selcase (&casev)[N]) {
    return _chanselect(&casev[0], N);
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

}   // golang::
#endif  // __cplusplus

#endif  // _PYGOLANG_GOLANG_H
