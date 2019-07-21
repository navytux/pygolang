#ifndef	_PYGOLANG_PANIC_H
#define	_PYGOLANG_PANIC_H

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

#ifdef	__cplusplus
extern "C" {
#endif

void panic(const char *arg);
const char *recover();
void bug(const char *arg);

struct _chan;
_chan *makechan(unsigned elemsize, unsigned size);
void chansend(_chan *ch, void *ptx);
bool chanrecv_(_chan *ch, void *prx);
void chanrecv(_chan *ch, void *prx);
void chanclose(_chan *ch);
unsigned chanlen(_chan *ch);

#ifdef __cplusplus
}
#endif


// chan<T> provides type-safe wrapper over _chan.
template<typename T>
struct chan {
    _chan *_ch;

    chan(unsigned size) {
        _ch = makechan(sizeof(T), size);
        if (_ch == NULL)
            throw std::bad_alloc();
    }

    // XXX free on dtor? ref-count? (i.e. shared_ptr ?)

    void send(T *ptx)   { chansend(_ch, ptx);           }
    bool recv_(T *prx)  { return chanrecv_(_ch, prx);   }
    void recv(T *prx)   { chanrecv(_ch, prx);           }
    void close()        { chanclose(_ch);               }
    unsigned len()      { return chanlen(_ch);          }
};

#endif	// _PYGOLANG_PANIC_H
