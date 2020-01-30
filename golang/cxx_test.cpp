// Copyright (C) 2020  Nexedi SA and Contributors.
//                     Kirill Smelkov <kirr@nexedi.com>
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

#include "golang/cxx.h"
#include "golang/_testing.h"
using namespace golang;
using std::tie;

void _test_cxx_dict() {
    cxx::dict<string, int> d;
    d["abc"] = 1;
    d["def"] = 2;

    // has
    ASSERT(d.has("abc"));
    ASSERT(d.has("def"));
    ASSERT(!d.has("zzz"));

    // get
    ASSERT_EQ(d.get("abc"), 1);
    ASSERT_EQ(d.get("def"), 2);
    ASSERT_EQ(d.get("zzz"), 0);

    int v; bool ok;

    // get_
    tie(v, ok) = d.get_("abc");
    ASSERT_EQ(v, 1); ASSERT_EQ(ok, true);

    tie(v, ok) = d.get_("def");
    ASSERT_EQ(v, 2); ASSERT_EQ(ok, true);

    tie(v, ok) = d.get_("zzz");
    ASSERT_EQ(v, 0); ASSERT_EQ(ok, false);

    // pop / pop_
    ASSERT_EQ(d.pop("zzz"), 0);
    tie(v, ok) = d.pop_("zzz");
    ASSERT_EQ(v, 0); ASSERT_EQ(ok, false);

    ASSERT(d.has("def"));
    ASSERT_EQ(d.pop("def"), 2);
    ASSERT(!d.has("def"));
    ASSERT_EQ(d.pop("def"), 0);
    ASSERT(!d.has("def"));

    ASSERT(d.has("abc"));
    tie(v, ok) = d.pop_("abc");
    ASSERT_EQ(v, 1); ASSERT_EQ(ok, true);
    ASSERT(!d.has("abc"));
    tie(v, ok) = d.pop_("abc");
    ASSERT_EQ(v, 0); ASSERT_EQ(ok, false);
}

void _test_cxx_set() {
    cxx::set<string> s;
    s.insert("abc");
    s.insert("def");

    // has
    ASSERT(s.has("abc"));
    ASSERT(s.has("def"));
    ASSERT(!s.has("zzz"));

    // has after erase
    s.erase("zzz");
    ASSERT(s.has("abc"));
    ASSERT(s.has("def"));
    ASSERT(!s.has("zzz"));

    s.erase("def");
    ASSERT(s.has("abc"));
    ASSERT(!s.has("def"));
    ASSERT(!s.has("zzz"));

    s.erase("abc");
    ASSERT(!s.has("abc"));
    ASSERT(!s.has("def"));
    ASSERT(!s.has("zzz"));
}
