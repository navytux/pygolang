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

// Library Libgolang provides Go-like features for C and C++.
//
// Library Libgolang provides goroutines, channels with Go semantic and other
// accompanying features. The library consists of high-level type-safe C++ API,
// and low-level unsafe C API. The low-level C API was inspired by Libtask[1]
// and Plan9/Libthread[2].
//
// The primary motivation for Libgolang is to serve as runtime for golang.pyx -
// - Cython part of Pygolang project. However Libgolang is independent of
// Python and should be possible to use in standalone C/C++ projects.
//
// Brief description of Libgolang API follows:
//
// C++-level API
//
//  - `go` spawns new task.
//  - `chan<T>`, and `select` provide channels with Go semantic and automatic
//    lifetime management.
//  - `sleep` pauses current task.
//  - `panic` throws exception that represent C-level panic.
//
// For example:
//
//      chan<int> ch = makechan<int>(); // create new channel
//      go(worker, ch, 1);              // spawn worker(chan<int>, int)
//      ch.send(1)
//      j = ch.recv()
//
//      _ = select({
//          _default,       // 0
//          ch.sends(&i),   // 1
//          ch.recvs(&j),   // 2
//      });
//      if (_ == 0)
//          // default case selected
//      if (_ == 1)
//          // case 1 selected: i sent to ch
//      if (_ == 2)
//          // case 2 selected: j received from ch
//
//      if (<bug condition>)
//          panic("bug");
//
//
// C-level API
//
//  - `_taskgo` spawns new task.
//  - `_makechan` creates raw channel with Go semantic.
//  - `_chanxincref` and `_chanxdecref` manage channel lifetime.
//  - `_chansend` and `_chanrecv` send/receive over raw channel.
//  - `_chanselect`, `_selsend`, `_selrecv`, ... provide raw select functionality.
//  - `tasknanosleep` pauses current task.
//
//
// Runtimes
//
// Libgolang, before being used, must be initialized with particular runtime
// plugin, which tailors Libgolang to particular execution environment. See
// `_libgolang_init` and `_libgolang_runtime_ops` for description of a runtime.
//
// Pygolang - the parent project of Libgolang - comes with two Libgolang runtimes:
//
//  - "thread" - a runtime that is based on OS threads, and
//  - "gevent" - a runtime that is based on greenlet and gevent.
//
// Once again, Libgolang itself is independent from Python, and other runtimes
// are possible.
//
//
// [1] Libtask: a Coroutine Library for C and Unix. https://swtch.com/libtask.
// [2] http://9p.io/magic/man2html/2/thread.

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

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
// (most of the functions are documented in libgolang.cpp)

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
LIBGOLANG_API int  _chanrefcnt(_chan *ch);
LIBGOLANG_API void _chansend(_chan *ch, const void *ptx);
LIBGOLANG_API void _chanrecv(_chan *ch, void *prx);
LIBGOLANG_API bool _chanrecv_(_chan *ch, void *prx);
LIBGOLANG_API void _chanclose(_chan *ch);
LIBGOLANG_API unsigned _chanlen(_chan *ch);
LIBGOLANG_API unsigned _chancap(_chan *ch);

enum _chanop {
    _CHANSEND   = 0,
    _CHANRECV   = 1,
    _DEFAULT    = 2,
};

// _selcase represents one select case.
typedef struct _selcase {
    _chan           *ch;    // channel
    enum _chanop    op;     // chansend/chanrecv/default
    void            *data;  // chansend: ptx; chanrecv: prx
    bool            *rxok;  // chanrecv: where to save ok if !NULL; otherwise not used
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
        .op     = _CHANRECV,
        .data   = prx,
        .rxok   = pok,
    };
    return _;
}

// _default represents default case for _chanselect.
extern LIBGOLANG_API const _selcase _default;


// libgolang runtime - the runtime must be initialized before any other libgolang use.
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

    // nanotime should return current time since EPOCH in nanoseconds.
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

#include <exception>
#include <functional>
#include <initializer_list>
#include <memory>
#include <type_traits>
#include <utility>

namespace golang {

// go provides type-safe wrapper over _taskgo.
template<typename F, typename... Argv>  // F = std::function<void(Argv...)>
static inline void go(F /*std::function<void(Argv...)>*/ f, Argv... argv) {
    typedef std::function<void(void)> Frun;
    Frun *frun = new Frun (std::bind(f, argv...));
    _taskgo([](void *_frun) {
        std::unique_ptr<Frun> frun (reinterpret_cast<Frun*>(_frun));
        (*frun)();
        // frun deleted here on normal exit or panic.
    }, frun);
}

template<typename T> class chan;
template<typename T> static chan<T> makechan(unsigned size=0);

// chan<T> provides type-safe wrapper over _chan.
//
// chan<T> is automatically reference-counted and is safe to use from multiple
// goroutines simultaneously.
template<typename T>
class chan {
    _chan *_ch;

public:
    inline chan() { _ch = NULL; } // nil channel if not explicitly initialized
    friend chan<T> makechan<T>(unsigned size);
    inline ~chan() { _chanxdecref(_ch); _ch = NULL; }

    // = nil
    inline chan(nullptr_t) { _ch = NULL; }
    inline chan& operator=(nullptr_t) { _chanxdecref(_ch); _ch = NULL; return *this; }
    // copy
    inline chan(const chan& from) { _ch = from._ch; _chanxincref(_ch); }
    inline chan& operator=(const chan& from) {
        if (this != &from) {
            _chanxdecref(_ch); _ch = from._ch; _chanxincref(_ch);
        }
        return *this;
    }
    // move
    inline chan(chan&& from) { _ch = from._ch; from._ch = NULL; }
    inline chan& operator=(chan&& from) {
        if (this != &from) {
            _chanxdecref(_ch); _ch = from._ch; from._ch = NULL;
        }
        return *this;
    }

    // _chan does plain memcpy to copy elements.
    // TODO allow all types (e.g. element=chan )
    static_assert(std::is_trivially_copyable<T>::value, "TODO chan<T>: T copy is not trivial");

    // send/recv/close
    inline void send(const T &ptx)    const  { _chansend(_ch, &ptx);                  }
    inline T recv()                   const  { T rx; _chanrecv(_ch, &rx); return rx;  }
    inline std::pair<T,bool> recv_()  const  { T rx; bool ok = _chanrecv_(_ch, &rx);
                                               return std::make_pair(rx, ok);         }
    inline void close()               const  { _chanclose(_ch);                       }

    // send/recv in select

    // ch.sends creates `ch.send(*ptx)` case for select.
    [[nodiscard]] inline _selcase sends(const T *ptx) const { return _selsend(_ch, ptx); }

    // ch.recvs creates `*prx = ch.recv()` case for select.
    //
    // if pok is provided the case is extended to `[*prx, *pok] = ch.recv_()`
    // if both prx and pok are omitted the case is reduced to `ch.recv()`.
    [[nodiscard]] inline _selcase recvs(T *prx=NULL, bool *pok=NULL) const {
        return _selrecv_(_ch, prx, pok);
    }

    // length/capacity
    inline unsigned len()             const  { return _chanlen(_ch); }
    inline unsigned cap()             const  { return _chancap(_ch); }

    // compare wrt nil
    inline bool operator==(nullptr_t) const  { return (_ch == NULL); }
    inline bool operator!=(nullptr_t) const  { return (_ch != NULL); }

    // compare wrt chan
    inline bool operator==(const chan<T>& ch2) const { return (_ch == ch2._ch); }
    inline bool operator!=(const chan<T>& ch2) const { return (_ch != ch2._ch); }

    // for testing
    inline _chan *_rawchan() const     { return _ch; }
};

// makechan<T> makes new chan<T> with capacity=size.
template<typename T> static inline
chan<T> makechan(unsigned size) {
    chan<T> ch;
    unsigned elemsize = std::is_empty<T>::value
        ? 0          // eg struct{} for which sizeof() gives 1 - *not* 0
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

// select, together with chan<T>.sends and chan<T>.recvs, provide type-safe
// wrappers over _chanselect and _selsend/_selrecv/_selrecv_.
//
// Usage example:
//
//   _ = select({
//       ch1.recvs(&v),         // 0
//       ch2.recvs(&v, &ok),    // 1
//       ch2.sends(&v),         // 2
//       _default,              // 3
//   })
static inline                       // select({case1, case2, case3})
int select(const std::initializer_list<const _selcase> &casev) {
    return _chanselect(casev.begin(), casev.size());
}

template<size_t N> static inline    // select(casev_array)
int select(const _selcase (&casev)[N]) {
    return _chanselect(&casev[0], N);
}


namespace time {

// sleep pauses current goroutine for at least dt seconds.
LIBGOLANG_API void sleep(double dt);

// now returns current time in seconds.
LIBGOLANG_API double now();

}   // golang::time::

}   // golang::
#endif  // __cplusplus

#endif  // _NXD_LIBGOLANG_H
