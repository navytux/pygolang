#ifndef _NXD_LIBGOLANG_H
#define _NXD_LIBGOLANG_H

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
#include <stdint.h>
#include <stdbool.h>

// ---- C-level API that is always available ----

// XXX annotate with LIBGOLANG_API

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

void _taskgo(void (*f)(void *arg), void *arg);
void _tasknanosleep(uint64_t dt);
uint64_t _nanotime(void);

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


// libgolang runtime - the runtime must be initialized before any other libgolang use
typedef struct _libgolang_sema _libgolang_sema;
typedef enum _libgolang_runtime_flags {
    // it is not safe to access goroutine's stack memory while the goroutine is parked.
    //
    // for example gevent/greenlet/stackless use it because they copy g's stack
    // to heap on park and back on unpark. This way if objects on g's stack
    // were accessed while g was parked it would be memory of another g's stack.
    STACK_DEAD_WHILE_PARKED = 1,    // XXX -> STACK_SWAPPED_WHILE_PACKED ?
} _libgolang_runtime_flags;
typedef struct _libgolang_runtime_ops {
    _libgolang_runtime_flags    flags;

    // go should spawn a task (coroutine/thread/...).
    void    (*go)(void (*f)(void *), void *arg);

    // sema_alloc should allocate a semaphore.
    // if allocation fails it must return NULL.
    _libgolang_sema* (*sema_alloc)(void);

    // sema_free should release previously allocated semaphore.
    // libgolang guarantees to call it only once and only for a semaphore
    // previously successfully allocated via sema_alloc.
    void             (*sema_free)   (_libgolang_sema*);

    // sema_acquire/sema_release should acquire/release live semaphore allocated via sema_alloc.
    void             (*sema_acquire)(_libgolang_sema*);
    void             (*sema_release)(_libgolang_sema*);

    // nanosleep should pause current goroutine for at least dt nanoseconds.
    // nanosleep(0) is not noop - such call must be at least yielding to other goroutines.
    void        (*nanosleep)(uint64_t dt);

    // nanotime should return current time since EPOCH in nanoseconnds.
    uint64_t    (*nanotime)(void);

} _libgolang_runtime_ops;

void _libgolang_init(const _libgolang_runtime_ops *runtime_ops);


// for testing
int _tchanrecvqlen(_chan *ch);
int _tchansendqlen(_chan *ch);
extern void (*_tblockforever)(void);

#ifdef __cplusplus
}}
#endif


// ---- C++-level API that is available when compiling with C++ ----

#ifdef __cplusplus

#include <functional>
#include <tuple>
#include <exception>        // bad_alloc & co
#include <initializer_list>

namespace golang {

// go provides type-safe wrapper over _taskgo.
template<typename F, typename... Argv>  // XXX F -> function<void(Argv...)>
void go(F /*std::function<void(Argv...)>*/ f, Argv... argv) {
    typedef std::function<void(void)> Frun;
    Frun *frun = new Frun (std::bind(f, argv...));
    _taskgo([](void *_frun) {
        Frun *frun = reinterpret_cast<Frun*>(_frun);
        (*frun)();
        delete frun;   // XXX -> defer
    }, frun);
}

template<typename T> class chan;
template<typename T> chan<T> makechan(unsigned size=0);
template<typename T> _selcase _send(chan<T>, const T*);     // XXX [[nodiscard]] ?
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

private:
    static chan<T> __make(unsigned elemsize, unsigned size);
};

template<typename T>
chan<T> chan<T>::__make(unsigned elemsize, unsigned size) {
    chan<T> ch;
    ch._ch = _makechan(elemsize, size);
    if (ch._ch == NULL)
        throw std::bad_alloc();
    return ch;
}

// makechan<T> makes new chan<T> with capacity=size.
template<typename T>
chan<T> makechan(unsigned size) {
    return chan<T>::__make(sizeof(T), size);
}

// makechan<void> makes new channel whose elements are empty.
template<> inline
chan<void> makechan(unsigned size) {
    return chan<void>::__make(0/* _not_ sizeof(void) which = 1*/, size);
}


// select, together with _send<T>, _recv<T> and _recv_<T>, provide type-safe
// wrappers over _chanselect and _selsend/_selrecv/_selrecv_.
//
// XXX select({}) example.
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

namespace time {

// XXX doc
static inline void nanosleep(uint64_t dt) {
    _tasknanosleep(dt);
}

// XXX doc, name=?
static inline uint64_t nanonow() {
    return _nanotime();
}

}   // golang::time::

}   // golang::
#endif  // __cplusplus

#endif  // _NXD_LIBGOLANG_H
