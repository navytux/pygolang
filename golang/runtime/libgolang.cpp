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
// See libgolang.h for library overview.

// Pygolang C part: provides runtime implementation of panic, etc.
//
// C++ (not C) is used:
// - to implement C-level panic (via C++ exceptions).

#include "golang/libgolang.h"

#include <exception>
#include <limits>
#include <mutex>        // lock_guard
#include <string>

#include <string.h>

// linux/list.h needs ARRAY_SIZE    XXX -> better use c.h or ccan/array_size.h ?
#ifndef ARRAY_SIZE
# define ARRAY_SIZE(A) (sizeof(A) / sizeof((A)[0]))
#endif
#include <linux/list.h>

using std::exception;
using std::numeric_limits;
using std::string;

namespace golang {

// ---- panic ----

struct PanicError : exception {
    const char *arg;
};

// panic throws exception that represents C-level panic.
// the exception can be caught at C++ level via try/catch and recovered via recover.
[[noreturn]] void panic(const char *arg) {
    PanicError _; _.arg = arg;
    throw _;
}

// recover recovers from exception thrown by panic.
// it returns: !NULL - there was panic with that argument. NULL - there was no panic.
// if another exception was thrown - recover rethrows it.
const char *recover() {
    // if PanicError was thrown - recover from it
    try {
        throw;
    } catch (PanicError &exc) {
        return exc.arg;
    }

    return NULL;
}


// bug indicates internal bug in golang implementation.
struct Bug : exception {
    const string msg;

    virtual const char *what() const throw() {
        return msg.c_str();
    }

    Bug(const string &msg) : msg("BUG: " + msg) {}
};

[[noreturn]] void bug(const char *msg) {
    throw Bug(msg);
}

// ---- runtime ----

// initially NULL to crash if runtime was not initialized
static const _libgolang_runtime_ops *_runtime = NULL;

void _libgolang_init(const _libgolang_runtime_ops *runtime_ops) {
    if (_runtime != NULL) // XXX better check atomically
        panic("libgolang: double init");
    _runtime = runtime_ops;
}

void _taskgo(void (*f)(void *), void *arg) {
    _runtime->go(f, arg);
}

void _tasknanosleep(uint64_t dt) {
    _runtime->nanosleep(dt);
}

uint64_t _nanotime() {
    return _runtime->nanotime();
}


// ---- semaphores ----

// Sema provides semaphore.
struct Sema {
    _libgolang_sema *_gsema;

    Sema();
    ~Sema();
    void acquire();
    void release();

private:
    Sema(const Sema&);      // don't copy
};

Sema::Sema() {
    Sema *sema = this;

    sema->_gsema = _runtime->sema_alloc();
    if (!sema->_gsema)
        panic("sema: alloc failed");
}

Sema::~Sema() {
    Sema *sema = this;

    _runtime->sema_free(sema->_gsema);
    sema->_gsema = NULL;
}

void Sema::acquire() {
    Sema *sema = this;
    _runtime->sema_acquire(sema->_gsema);
}

void Sema::release() {
    Sema *sema = this;
    _runtime->sema_release(sema->_gsema);
}

// Mutex provides mutex.
// currently implemented via Sema.
struct Mutex {
    void lock()     { _sema.acquire();  }
    void unlock()   { _sema.release();  }
    Mutex() {}

private:
    Sema _sema;
    Mutex(const Mutex&);    // don't copy
};

// with_lock mimics `with mu` from python.
#define with_lock(mu) std::lock_guard<Mutex> _with_lock_ ## __COUNTER__ (mu)

}   // golang::


// ---- golang::time:: ----

namespace golang {
namespace time {

void sleep(double dt) {
    if (dt <= 0)
        dt = 0;
    dt *= 1E9; // s -> ns
    if (dt > numeric_limits<uint64_t>::max())
        panic("sleep: dt overflow");
    uint64_t dt_ns = dt;
    _tasknanosleep(dt_ns);
}

double now() {
    uint64_t t_ns = _nanotime();
    double t_s = t_ns * 1E-9;   // no overflow possible
    return t_s;
}

}}  // golang::time::
