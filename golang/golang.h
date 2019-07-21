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

#ifdef __cplusplus
}
#endif

// chan<T> provides type-safe wrapper over _chan.
struct _chan;
template<typename T>
struct chan {
    _chan *ch;

    chan(unsigned size) {
        ch = makechan(sizeof(T), size);
        if (ch == NULL)
            throw std::bad_alloc();
    }

    // XXX free on dtor? ref-count? (i.e. shared_ptr ?)

    void send(T *ptx)   { ch->send(ptx);            }
    bool recv_(T *prx)  { return ch->recv_(prx);    }
    void recv(T *prx)   { ch->recv(prx);            }
    void close()        { ch->close();              }
    unsigned len()      { return ch->len();         }
};

#endif	// _PYGOLANG_PANIC_H
