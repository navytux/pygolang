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
    void  (*op)(_chan *, void *);   // chansend/chanrecv/default
    void  *data;                    // chansend: tx; chanrecv: rx
    bool  rxok;                     // tx: unused; rx: comma-ok after recv_
};

void _default(_chan *, void *);

bool _tchanblocked(_chan *ch, bool recv, bool send);

#ifdef __cplusplus
}
#endif


// ---- C++-level API that is available when compiling with C++ ----

#ifdef __cplusplus

#include <exception>    // bad_alloc & co

// chan<T> provides type-safe wrapper over _chan.
template<typename T>
struct chan {
    _chan *_ch;

    // = nil channel if not initialized
    chan() { _ch = 0; }

    // XXX copy = ok?
    // XXX free on dtor? ref-count? (i.e. shared_ptr ?)

    void send(T *ptx)   { _chansend(_ch, ptx);          }
    bool recv_(T *prx)  { return _chanrecv_(_ch, prx);  }
    void recv(T *prx)   { _chanrecv(_ch, prx);          }
    void close()        { _chanclose(_ch);              }
    unsigned len()      { return _chanlen(_ch);         }
};

template<typename T>
chan<T> makechan(unsigned size) {
    chan<T> ch;
    ch._ch = _makechan(sizeof(T), size);
    if (ch._ch == 0)
        throw std::bad_alloc();
    return ch;
}

#endif  // __cplusplus

#endif  // _PYGOLANG_GOLANG_H
