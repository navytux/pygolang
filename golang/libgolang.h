#ifndef _NXD_LIBGOLANG_H
#define _NXD_LIBGOLANG_H

// Copyright (C) 2018-2020  Nexedi SA and Contributors.
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
//  - `defer` schedules cleanup.
//  - `error` is the interface that represents errors.
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
//      defer([]() {
//          printf("leaving...\n");
//      });
//
//      if (<bug condition>)
//          panic("bug");
//
//
// Memory management
//
// C++-level API provides limited support for automatic memory management:
//
//  - `refptr` and `object` provide way to manage objects lifetime automatically.
//  - `newref` and `adoptref` can be used to convert raw pointer into refptr<T>.
//  - `global` should be used for global refptr pointers.
//
// For example:
//
//      // MyObject is defined via 2 classes: _MyObject + MyObject
//      typedef refptr<struct _MyObject> MyObject;
//      struct _MyObject : object {
//          int x;
//
//          // don't new - create only view NewMyObject()
//      private:
//          _MyObject();
//          ~_MyObject();
//          friend MyObject NewMyObject(int x);
//      public:
//          void decref();
//
//          // MyObject API
//          void do_something() {
//              ...
//          }
//      };
//
//      MyObject NewMyObject(int x) {
//          MyObject obj = adoptref(new _MyObject());
//          obj->x = x;
//          return obj;
//      }
//
//      _MyObject::_MyObject()  {}
//      _MyObject::~_MyObject() {}
//      void _MyObject::decref() {
//          if (__decref())
//              delete this;
//      }
//
//      ...
//
//      global<MyObject> gobj = NewMyObject(1); // global object instance
//
//      void myfunc() {
//          MyObject obj = NewMyObject(123);
//          ...
//          obj->x;                 // use data field of the object
//          obj->do_something();    // call method of the object
//          ...
//          // obj is automatically deallocated on function exit
//      }
//
//
// Interfaces
//
// C++-level API provides limited support for interfaces:
//
//  - `interface` is empty interface a-la interface{} in Go.
//  - `error` is the interface describing errors.
//
// There is no support for at-runtime interface construction for an object:
// a class must inherit from all interfaces that it wants to implement.
//
//
// C-level API
//
//  - `_taskgo` spawns new task.
//  - `_makechan` creates raw channel with Go semantic.
//  - `_chanxincref` and `_chanxdecref` manage channel lifetime.
//  - `_chansend` and `_chanrecv` send/receive over raw channel.
//  - `_chanselect`, `_selsend`, `_selrecv`, ... provide raw select functionality.
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
// Additional packages
//
// Libgolang, besides goroutines and channels, provides additional packages
// that mirror Go analogs. See for example golang/time.h, golang/sync.h, etc.
//
//
// [1] Libtask: a Coroutine Library for C and Unix. https://swtch.com/libtask.
// [2] http://9p.io/magic/man2html/2/thread.

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

// DSO symbols visibility (based on https://gcc.gnu.org/wiki/Visibility)
#if defined _WIN32 || defined __CYGWIN__
  #define LIBGOLANG_DSO_EXPORT __declspec(dllexport)
  #define LIBGOLANG_DSO_IMPORT __declspec(dllimport)
#elif __GNUC__ >= 4
  #define LIBGOLANG_DSO_EXPORT __attribute__ ((visibility ("default")))
  #define LIBGOLANG_DSO_IMPORT __attribute__ ((visibility ("default")))
#else
  #define LIBGOLANG_DSO_EXPORT
  #define LIBGOLANG_DSO_IMPORT
#endif

#if BUILDING_LIBGOLANG
#  define LIBGOLANG_API LIBGOLANG_DSO_EXPORT
#else
#  define LIBGOLANG_API LIBGOLANG_DSO_IMPORT
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

enum _selflags {
    // _INPLACE_DATA indicates that select case data is stored in
    // _selcase.itxrx instead of in *_selcase.ptxrx .
    // XXX can be used only for send for now. In the future, for symmetry, we
    // might want to allow _INPLACE_DATA for recv too.
    _INPLACE_DATA   = 1,
};


// _selcase represents one select case.
typedef struct _selcase {
    _chan           *ch;        // channel
    enum _chanop    op    : 8;  // chansend/chanrecv/default
    enum _selflags  flags : 8;  // e.g. _INPLACE_DATA
    unsigned        user  : 8;  // arbitrary value that can be set by user
                                // (e.g. pyselect stores channel type here)
    unsigned              : 8;
    union {
        void        *ptxrx;     // chansend: ptx; chanrecv: prx
        uint64_t     itxrx;     // used instead of .ptxrx if .flags&_INPLACE_DATA != 0
    };
    bool            *rxok;      // chanrecv: where to save ok if !NULL; otherwise not used

#ifdef __cplusplus
    // ptx returns pointer to data to send for this case.
    // .op must be _CHANSEND.
    LIBGOLANG_API const void *ptx() const;

    // prx returns pointer for this case to receive data into.
    // .op must be _CHANRECV.
    LIBGOLANG_API void *prx() const;
#endif
} _selcase;

LIBGOLANG_API int _chanselect(const _selcase *casev, int casec);

// _selsend creates `_chansend(ch, ptx)` case for _chanselect.
static inline
_selcase _selsend(_chan *ch, const void *ptx) {
    _selcase _ = {
        .ch     = ch,
        .op     = _CHANSEND,
        .flags  = (enum _selflags)0,
        .user   = 0xff,
    };
    _   .ptxrx  = (void *)ptx;
    _   .rxok   = NULL;
    return _;
}

// _selrecv creates `_chanrecv(ch, prx)` case for _chanselect.
static inline
_selcase _selrecv(_chan *ch, void *prx) {
    _selcase _ = {
        .ch     = ch,
        .op     = _CHANRECV,
        .flags  = (enum _selflags)0,
        .user   = 0xff,
    };
    _   .ptxrx  = prx;
    _   .rxok   = NULL;
    return _;
}

// _selrecv_ creates `*pok = _chanrecv_(ch, prx)` case for _chanselect.
static inline
_selcase _selrecv_(_chan *ch, void *prx, bool *pok) {
    _selcase _ = {
        .ch     = ch,
        .op     = _CHANRECV,
        .flags  = (enum _selflags)0,
        .user   = 0xff,
    };
    _   .ptxrx  = prx;
    _   .rxok   = pok;
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

#include <atomic>
#include <cstddef>
#include <exception>
#include <functional>
#include <initializer_list>
#include <memory>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

namespace golang {

// nil is alias for nullptr and NULL; Nil - for std::nullptr_t;
using Nil = std::nullptr_t;
constexpr Nil nil = nullptr;

// string is alias for std::string.
using string = std::string;

// func is alias for std::function.
template<typename F>
using func = std::function<F>;

// go provides type-safe wrapper over _taskgo.
template<typename F, typename... Argv>  // F = func<void(Argv...)>
static inline void go(F /*func<void(Argv...)>*/ f, Argv... argv) {
    typedef func<void()> Frun;
    Frun *frun = new Frun (std::bind(f, argv...));
    _taskgo([](void *_frun) {
        std::unique_ptr<Frun> frun (reinterpret_cast<Frun*>(_frun));
        (*frun)();
        // frun deleted here on normal exit or panic.
    }, frun);
}

template<typename T> class chan;
template<typename T> static chan<T> makechan(unsigned size=0);
template<typename T> static chan<T> _wrapchan(_chan *_ch);

// chan<T> provides type-safe wrapper over _chan.
//
// chan<T> is automatically reference-counted and is safe to use from multiple
// goroutines simultaneously.
template<typename T>
class chan {
    _chan *_ch;

public:
    inline chan() { _ch = nil; } // nil channel if not explicitly initialized
    friend chan<T> makechan<T>(unsigned size);
    friend chan<T> _wrapchan<T>(_chan *_ch);
    inline ~chan() { _chanxdecref(_ch); _ch = nil; }

    // = nil
    inline chan(Nil) { _ch = nil; }
    inline chan& operator=(Nil) { _chanxdecref(_ch); _ch = nil; return *this; }
    // copy
    inline chan(const chan& from) { _ch = from._ch; _chanxincref(_ch); }
    inline chan& operator=(const chan& from) {
        if (this != &from) {
            _chanxdecref(_ch); _ch = from._ch; _chanxincref(_ch);
        }
        return *this;
    }
    // move
    inline chan(chan&& from) { _ch = from._ch; from._ch = nil; }
    inline chan& operator=(chan&& from) {
        if (this != &from) {
            _chanxdecref(_ch); _ch = from._ch; from._ch = nil;
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
    [[nodiscard]] inline _selcase recvs(T *prx=nil, bool *pok=nil) const {
        return _selrecv_(_ch, prx, pok);
    }

    // length/capacity
    inline unsigned len()       const  { return _chanlen(_ch); }
    inline unsigned cap()       const  { return _chancap(_ch); }

    // compare wrt nil
    inline bool operator==(Nil) const  { return (_ch == nil); }
    inline bool operator!=(Nil) const  { return (_ch != nil); }

    // compare wrt chan
    inline bool operator==(const chan<T>& ch2) const { return (_ch == ch2._ch); }
    inline bool operator!=(const chan<T>& ch2) const { return (_ch != ch2._ch); }

    // for testing
    inline _chan *_rawchan() const     { return _ch; }
};

// _elemsize<T> returns element size for chan<T>.
template<typename T> static inline
unsigned _elemsize() {
    return std::is_empty<T>::value
        ? 0          // eg struct{} for which sizeof() gives 1 - *not* 0
        : sizeof(T);
}

// makechan<T> makes new chan<T> with capacity=size.
template<typename T> static inline
chan<T> makechan(unsigned size) {
    chan<T> ch;
    ch._ch = _makechan(_elemsize<T>(), size);
    return ch;
}

// _wrapchan<T> wraps raw channel with chan<T>.
// raw channel must be either nil or its element size must correspond to T.
LIBGOLANG_API void __wrapchan(_chan *_ch, unsigned elemsize);
template<typename T> static inline
chan<T> _wrapchan(_chan *_ch) {
    chan<T> ch;
    __wrapchan(_ch, _elemsize<T>());
    ch._ch = _ch;
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

static inline                       // select(vector<casev>)
int select(const std::vector<_selcase> &casev) {
    return _chanselect(&casev[0], casev.size());
}

// defer(f) mimics `defer f()` from golang.
// NOTE contrary to Go f is called at end of current scope, not function.
#define defer(f) golang::_deferred _defer_(__COUNTER__) (f)
#define _defer_(counter)    _defer_2(counter)
#define _defer_2(counter)   _defer_##counter
struct _deferred {
    typedef func<void()> F;
    F f;

    _deferred(F f) : f(f) {}
    ~_deferred() { f(); }
private:
    _deferred(const _deferred&);    // don't copy
    _deferred(_deferred&&);         // don't move
};


// ---- reference-counted objects ----
// C++ does not have garbage-collector -> libgolang provides illusion of GC
// via reference counting support.

template<typename T> class refptr;
template<typename T> refptr<T> adoptref(T *_obj);
template<typename T> refptr<T> newref  (T *_obj);
template<typename R> class global;

// refptr<T> is smart pointer to T which manages T lifetime via reference counting.
//
// T must provide incref/decref methods for example via inheriting from object.
// incref/decref must be safe to use from multiple threads simultaneously.
//
// See also interface.
template<typename T>
class refptr {
    T *_obj;

    typedef T obj_type;
    friend global<refptr<T>>;

public:
    // nil if not explicitly initialized
    inline refptr()                 { _obj = nil;  }

    inline ~refptr() {
        if (_obj != nil) {
            _obj->decref();
            _obj = nil;
        }
    }

    // = nil
    inline refptr(Nil)              { _obj = nil;  }
    inline refptr& operator=(Nil) {
        if (_obj != nil)
            _obj->decref();
        _obj = nil;
        return *this;
    }

    // copy
    inline refptr(const refptr& from) {
        _obj = from._obj;
        if (_obj != nil)
            _obj->incref();
    }
    inline refptr& operator=(const refptr& from) {
        if (this != &from) {
            if (_obj != nil)
                _obj->decref();
            _obj = from._obj;
            if (_obj != nil)
                _obj->incref();
        }
        return *this;
    }

    // move
    inline refptr(refptr&& from) {
        _obj = from._obj;
        from._obj = nil;
    }
    inline refptr& operator=(refptr&& from) {
        if (this != &from) {
            if (_obj != nil)
                _obj->decref();
            _obj = from._obj;
            from._obj = nil;
        }
        return *this;
    }

    // create from raw pointer
    friend refptr<T> adoptref<T>(T *_obj);
    friend refptr<T> newref<T>  (T *_obj);

    // compare wrt nil
    inline bool operator==(Nil) const { return (_obj == nil); }
    inline bool operator!=(Nil) const { return (_obj != nil); }

    // compare wrt refptr
    inline bool operator==(const refptr& p2) const { return (_obj == p2._obj);  }
    inline bool operator!=(const refptr& p2) const { return (_obj != p2._obj);  }

    // dereference, so that e.g. p->method() automatically works as p._obj->method().
    inline T* operator-> () const   { return _obj;  }
    inline T& operator*  () const   { return *_obj; }

    // access to raw pointer
    inline T *_ptr() const          { return _obj;  }
};

// global<refptr<T>> is like refptr<T> but does not deallocate the object on pointer destruction.
//
// The sole reason for global to exist is to avoid race condition on program exit
// when global refptr<T> pointer is destructed, but another thread that
// continues to run, accesses the pointer.
//
// global<X> should be interoperable where X is used, for example:
//
//      const global<error> ErrSomething = errors::New("abc")
//      error err = ...;
//      if (err == ErrSomething)
//          ...
template<typename R>
class global {
    // implementation note:
    //  - don't use base parent for refptr and global with common functionality
    //    in parent, because e.g. copy-constructors cannot-be inherited.
    //  - don't use _refptr<T, bool global> template not to make compiler error
    //    messages longer for common refptr<T> case.
    //
    // -> just mimic refptr<T> functionality with a bit of duplication.
    typedef typename R::obj_type T;
    T *_obj;

public:
    // global does not release reference to its object, nor clears ._obj
    inline ~global() {}

    // cast global<refptr<T>> -> to refptr<T>
    operator refptr<T> () const {
        return newref<T>(_obj);
    }

    // nil if not explicitly initialized
    inline global()                 { _obj = nil;   }

    // init from refptr<T>
    inline global(const refptr<T>& from) {
        _obj = from._obj;
        if (_obj != nil)
            _obj->incref();
    }

    // = nil
    inline global(Nil)              { _obj = nil;   }
    inline global& operator=(Nil) {
        if (_obj != nil)
            _obj->decref();
        _obj = nil;
        return *this;
    }

    // copy - no need due to refptr<T> cast
    // move - no need due to refptr<T> cast

    // compare wrt nil
    inline bool operator==(Nil) const { return (_obj == nil); }
    inline bool operator!=(Nil) const { return (_obj != nil); }

    // compare wrt refptr
    inline bool operator==(const refptr<T>& p2) const { return (_obj == p2._obj);  }
    inline bool operator!=(const refptr<T>& p2) const { return (_obj != p2._obj);  }

    // dereference, so that e.g. p->method() automatically works as p._obj->method().
    inline T* operator-> () const   { return _obj;  }
    inline T& operator*  () const   { return *_obj; }

    // access to raw pointer
    inline T *_ptr() const          { return _obj;  }
};

// adoptref wraps raw T* pointer into refptr<T> and transfers object ownership to it.
//
// The object is assumed to have reference 1 initially.
// Usage example:
//
//      refptr<MyClass> p = adoptref(new MyClass());
//      ...
//      // the object will be deleted when p goes out of scope
template<typename T>
inline refptr<T> adoptref(T *_obj) {
    refptr<T> p;
    p._obj = _obj;
    return p;
}

// newref wraps raw T* pointer into refptr<T>.
//
// Created refptr holds new reference onto wrapped object.
// Usage example:
//
//      doSomething(MyClass *obj) {
//          refptr<MyClass> p = newref(obj);
//          ...
//          // obj is guaranteed to stay alive until p stays alive
//      }
template<typename T>
inline refptr<T> newref(T *_obj) {
    refptr<T> p;
    p._obj = _obj;
    if (_obj != nil)
        _obj->incref();
    return p;
}

// object is the base-class for on-heap objects.
//
// It provides reference-counting functionality, which, when used via refptr,
// provides automatic memory management for allocated objects.
//
// object provides incref & __decref - the user must implement decref(*).
//
// (*) this way we don't require destructor to be virtual.
class object {
    std::atomic<int> _refcnt;    // reference counter for the object

protected:
    LIBGOLANG_API object();
    LIBGOLANG_API ~object();
    LIBGOLANG_API bool __decref();

public:
    LIBGOLANG_API void incref();
    LIBGOLANG_API int  refcnt() const;
};

// interface is empty interface a-la interface{} in Go.
//
// It is the base class of all interfaces.
//
// Even if the interface is empty, it requires memory-management methods to be
// present. See refptr for details.
struct _interface {
    virtual void incref() = 0;
    virtual void decref() = 0;

protected:
    // don't use destructor -> use decref
    ~_interface();
};
typedef refptr<_interface> interface;


// error is the interface describing errors.
struct _error : _interface {
    virtual string Error() = 0;
};
typedef refptr<_error> error;

// an error can additionally provide Unwrap method if it wraps another error.
struct _errorWrapper : _error {
    virtual error Unwrap() = 0;
};
typedef refptr<_errorWrapper> errorWrapper;

}   // golang::


// std::hash<refptr>
namespace std {

template<typename T> struct hash<golang::refptr<T>> {
    std::size_t operator()(const golang::refptr<T>& p) const noexcept {
        return hash<T*>()(p._ptr());
    }
};

}   // std::


#endif  // __cplusplus

#endif  // _NXD_LIBGOLANG_H
