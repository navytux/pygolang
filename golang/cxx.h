#ifndef _NXD_LIBGOLANG_CXX_H
#define _NXD_LIBGOLANG_CXX_H

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

// Package cxx provides C++ amendments to be used by libgolang and its users.

#include <unordered_map>
#include <unordered_set>
#include <tuple>

// golang::cxx::
namespace golang {
namespace cxx {

using std::tuple;
using std::tie;
using std::make_tuple;

// dict wraps unordered_map into ergonomic interface.
template<typename Key, typename Value>
struct dict : std::unordered_map<Key, Value> {
    // has returns whether dict has element k.
    bool has(const Key &k) const {
        const dict &d = *this;
        return d.find(k) != d.end();
    }

    // get implements `d[k] -> v`.
    Value get(const Key &k) const {
        Value v; bool _; tie(v, _) = get_(k);
        return v;
    }

    // get_ implements `d[k] -> (v, ok)`.
    tuple<Value, bool> get_(const Key &k) const {
        const dict &d = *this;
        auto _ = d.find(k);
        if (_ == d.end())
            return make_tuple(Value(), false);
        return make_tuple(_->second, true);
    }

    // pop implements `d[k] -> v; del d[k]`.
    Value pop(const Key &k) {
        Value v; bool _; tie(v, _) = pop_(k);
        return v;
    }

    // pop_ implements `d[k] -> (v, ok); del d[k]`.
    tuple<Value, bool> pop_(const Key &k) {
        dict &d = *this;
        auto _ = d.find(k);
        if (_ == d.end())
            return make_tuple(Value(), false);
        Value v = _->second;
        d.erase(_);
        return make_tuple(v, true);
    }
};

// set wraps unordered_set into ergonomic interface.
template<typename Key>
struct set : std::unordered_set<Key> {
    // has returns whether set has element k.
    bool has(const Key &k) const {
        const set &s = *this;
        return s.find(k) != s.end();
    }
};


}}  // golang::cxx::


#endif  // _NXD_LIBGOLANG_CXX_H
