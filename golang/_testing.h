#ifndef _NXD_LIBGOLANG__TESTING_H
#define _NXD_LIBGOLANG__TESTING_H

// Copyright (C) 2019-2020  Nexedi SA and Contributors.
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

// Package _testing provides internal bits for testing libgolang and
// accompanying packages.

#include "golang/libgolang.h"
#include <sstream>
#include <string.h>
#include <vector>

// std::to_string<T> - provide missing pieces.
namespace std {
using namespace golang;

// string -> string (not in STL, huh ?!)
string to_string(const string& s) { return s; }

// error -> string
string to_string(error err) { return (err == nil) ? "nil" : err->Error(); }

// vector<T> -> string
template<typename T>
string to_string(const vector<T>& v) {
    std::ostringstream ss;
    ss << "[";
    int i = 0;
    for (auto x : v) {
        if (i++ != 0)
            ss << " ";
        ss << x << ",";
    }
    ss << "]";

    return ss.str();
}

}   // std::


// golang::_testing::
namespace golang {
namespace _testing {

#define __STR(X)  #X
#define STR(X)    __STR(X)
#define ASSERT(COND) do {   \
    if (!(COND))            \
        panic(__FILE__ ":" STR(__LINE__) " assert `" #COND "` failed"); \
} while(0)

#define ASSERT_EQ(A, B) golang::_testing::__assert_eq(__FILE__ ":" STR(__LINE__), #A, A, B)
template<typename T, typename U>
void __assert_eq(const string& loc, const string &expr, const T &have, const U &want) {
    if (have != want) {
        string emsg = loc + ": " + expr + "\n";
        emsg += "have: '" + std::to_string(have) + "'\n";
        emsg += "want: '" + std::to_string(want) + "'";

        panic(strdup(emsg.c_str()));    // XXX strdup because panic just saves char* pointer
    }
};

}}  // golang::_testing::


#endif  // _NXD_LIBGOLANG__TESTING_H
