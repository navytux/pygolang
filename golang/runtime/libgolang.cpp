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
#include <string>

using std::exception;
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

}   // golang::
