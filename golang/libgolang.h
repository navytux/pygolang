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

// DSO symbols visibility (based on https://gcc.gnu.org/wiki/Visibility)
#if defined _WIN32 || defined __CYGWIN__
  #ifdef BUILDING_LIBGOLANG
    #define LIBGOLANG_API __declspec(dllexport)
  #else
    #define LIBGOLANG_API __declspec(dllimport)
  #endif
#elif __GNUC__ >= 4
    #define LIBGOLANG_API __attribute__ ((visibility ("default")))
#else
    #define LIBGOLANG_API
#endif


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
LIBGOLANG_API void panic(const char *arg);
LIBGOLANG_API const char *recover(void);

LIBGOLANG_API void _taskgo(void (*f)(void *arg), void *arg);
LIBGOLANG_API void _tasknanosleep(uint64_t dt);
LIBGOLANG_API uint64_t _nanotime(void);

typedef struct _chan _chan;
LIBGOLANG_API _chan *_makechan(unsigned elemsize, unsigned size);
LIBGOLANG_API void _chanxincref(_chan *ch);
LIBGOLANG_API void _chanxdecref(_chan *ch);
LIBGOLANG_API void _chansend(_chan *ch, const void *ptx);
LIBGOLANG_API void _chanrecv(_chan *ch, void *prx);
LIBGOLANG_API bool _chanrecv_(_chan *ch, void *prx);
LIBGOLANG_API void _chanclose(_chan *ch);
LIBGOLANG_API unsigned _chanlen(_chan *ch);
LIBGOLANG_API unsigned _chancap(_chan *ch);

enum _chanop {
    _CHANSEND   = 0,
    _CHANRECV   = 1,
    _CHANRECV_  = 2,
    _DEFAULT    = 3,
};

// _selcase represents one select case.
typedef struct _selcase {
    _chan           *ch;    // channel
    enum _chanop    op;     // chansend/chanrecv/chanrecv_/default
    void            *data;  // chansend: ptx; chanrecv*: prx
    bool            *rxok;  // chanrecv_: where to save ok; otherwise not used
} _selcase;

LIBGOLANG_API int _chanselect(const _selcase *casev, int casec);

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
extern LIBGOLANG_API const _selcase _default;


// libgolang runtime - the runtime must be initialized before any other libgolang use
typedef struct _libgolang_sema _libgolang_sema;
typedef enum _libgolang_runtime_flags {
    // STACK_DEAD_WHILE_PARKED indicates that it is not safe to access
    // goroutine's stack memory while the goroutine is parked.
    //
    // for example gevent/greenlet/stackless use it because they copy g's stack
    // to heap on park and back on unpark. This way if objects on g's stack
    // were accessed while g was parked it would be memory of another g's stack.
    STACK_DEAD_WHILE_PARKED = 1,
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

LIBGOLANG_API void _libgolang_init(const _libgolang_runtime_ops *runtime_ops);


// for testing
LIBGOLANG_API int _tchanrecvqlen(_chan *ch);
LIBGOLANG_API int _tchansendqlen(_chan *ch);
LIBGOLANG_API extern void (*_tblockforever)(void);

#ifdef __cplusplus
}}
#endif


// ---- C++-level API that is available when compiling with C++ ----

#ifdef __cplusplus

#include <exception>        // bad_alloc & co
#include <functional>
#include <initializer_list>
#include <type_traits>
#include <utility>

namespace golang {

// go provides type-safe wrapper over _taskgo.
template<typename F, typename... Argv>  // XXX F -> function<void(Argv...)>
static inline void go(F /*std::function<void(Argv...)>*/ f, Argv... argv) {
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
template<typename T> [[nodiscard]] _selcase _send(chan<T>, const T*);
template<typename T> [[nodiscard]] _selcase _recv(chan<T>, T* = NULL);
template<typename T> [[nodiscard]] _selcase _recv_(chan<T>, T*, bool*);

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

    // _chan does plain memcpy to copy elements.
    // TODO allow all types (e.g. element=chan )
    static_assert(std::is_trivially_copyable<T>::value, "TODO chan<T>: T copy is not trivial");

    // TODO also support `ch << v`, `v << ch`, `v, ok << ch`
    // XXX  however C++ does not allow e.g. `<< ch`
    void send(const T &ptx)     { _chansend(_ch, &ptx);          }
    T recv()                    { T rx; _chanrecv(_ch, &rx); return rx; }
    std::pair<T,bool> recv_()   { T rx; bool ok = _chanrecv_(_ch, &rx);
                                  return std::make_pair(rx, ok); }

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
template<typename T> static inline
chan<T> makechan(unsigned size) {
    chan<T> ch;
    unsigned elemsize = std::is_empty<T>::value
        ? 0          // eg struct{} for which sizeof() gives 1
        : sizeof(T);
    ch._ch = _makechan(elemsize, size);
    if (ch._ch == NULL)
        throw std::bad_alloc();
    return ch;
}

// structZ is struct{}.
//
// it's a workaround for e.g. makechan<struct{}> giving
// "error: types may not be defined in template arguments".
struct structZ{};

// select, together with _send<T>, _recv<T> and _recv_<T>, provide type-safe
// wrappers over _chanselect and _selsend/_selrecv/_selrecv_.
//
// Usage example:
//
//   _ = select({
//       _recv(ch1, &v),        # 0
//       _recv_(ch2, &v, &ok),  # 1
//       _send(ch2, &v),        # 2
//       _default,              # 3
//   })
static inline                       // select({case1, case2, case3})
int select(const std::initializer_list<const _selcase> &casev) {
    return _chanselect(casev.begin(), casev.size());
}

template<size_t N> static inline    // select(casev_array)
int select(const _selcase (&casev)[N]) {
    return _chanselect(&casev[0], N);
}

// _send<T> creates `ch<T>.send(ptx)` case for select.
template<typename T> inline
_selcase _send(chan<T> ch, const T *ptx) {
    return _selsend(ch._ch, ptx);
}

// _recv<T> creates `ch<T>.recv(prx)` case for select.
template<typename T> inline
_selcase _recv(chan<T> ch, T *prx) {
    return _selrecv(ch._ch, prx);
}

// _recv_<T> creates `*pok = ch.recv_(prx)` case for select.
template<typename T> inline
_selcase _recv_(chan<T> ch, T *prx, bool *pok) {
    return _selrecv_(ch._ch, prx, pok);
}

namespace time {

// sleep pauses current goroutine for at least dt seconds.
static inline void sleep(double dt) {
    uint64_t dt_ns = dt * 1E9; // XXX overflow
    _tasknanosleep(dt_ns);
}

// now returns current time in seconds.
static inline double now() {
    uint64_t t_ns = _nanotime();
    double t_s = t_ns * 1E-9;   // XXX overflow
    return t_s;
}

}   // golang::time::

}   // golang::
#endif  // __cplusplus

#endif  // _NXD_LIBGOLANG_H
