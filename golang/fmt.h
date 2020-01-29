#ifndef _NXD_LIBGOLANG_FMT_H
#define _NXD_LIBGOLANG_FMT_H

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

// Package fmt mirrors Go package fmt.
//
//  - `sprintf` formats text into string.
//  - `errorf`  formats text into error.
//
// NOTE: with exception of %w, formatting rules are those of libc, not Go(*).
//
// See also https://golang.org/pkg/fmt for Go fmt package documentation.
//
// (*) errorf additionally handles Go-like %w to wrap an error similarly to
//     https://blog.golang.org/go1.13-errors .

#include <golang/libgolang.h>
#include <type_traits>

// golang::fmt::
namespace golang {
namespace fmt {

// sprintf formats text into string.
LIBGOLANG_API string sprintf(const string &format, ...);


// intseq<i1, i2, ...> and intrange<n> are used by errorf to handle %w.
namespace {
    // intseq<i1, i2, ...> provides compile-time integer sequence.
    // (std::integer_sequence is C++14 while libgolang targets C++11)
    template<int ...nv>
    struct intseq {
        // apppend<x> defines intseq<i1, i2, ..., x>.
        template<int x>
        struct append {
            using type = intseq<nv..., x>;
        };
    };

    // intrange<n> provides integer sequence intseq<0, 1, 2, ..., n-1>.
    template<int n>
    struct intrange;

    template<>
    struct intrange<0> {
        using type = intseq<>;
    };

    template<int n>
    struct intrange {
        using type = typename intrange<n-1>::type::template append<n-1>::type;
    };
}

// `errorf`  formats text into error.
//
// format suffix ": %w" is additionally handled as in Go with
// `errorf("... : %w", ..., err)` creating error that can be unwrapped back to err.
LIBGOLANG_API error ___errorf(const string& format, ...);
LIBGOLANG_API error ___errorfTryWrap(const string& format, error last_err, ...);
LIBGOLANG_API string ___error_str(error err);

// _errorf(..., err) tails here.
template<typename ...Headv>
inline error __errorf(std::true_type, const string& format, error last_err, Headv... headv) {
    return ___errorfTryWrap(format, last_err, headv..., ___error_str(last_err).c_str());
}

// _errorf(..., !err) tails here.
template<typename ...Headv, typename Last>
inline error __errorf(std::false_type, const string& format, Last last, Headv... headv) {
    return ___errorf(format, headv..., last);
}

template<typename ...Argv, int ...HeadIdxv>
inline error _errorf(intseq<HeadIdxv...>, const string& format, Argv... argv) {
    auto argt = std::make_tuple(argv...);
    auto last = std::get<sizeof...(argv)-1>(argt);
    return __errorf(std::is_same<decltype(last), error>(), format, last, std::get<HeadIdxv>(argt)...);
}

inline error errorf(const string& format) {
    return ___errorf(format);
}
template<typename ...Argv>
inline error errorf(const string& format, Argv... argv) {
    return _errorf(typename intrange<sizeof...(argv)-1>::type(), format, argv...);
}



// `const char *` overloads just to catch format mistakes as
// __attribute__(format) does not work with std::string.
LIBGOLANG_API string sprintf(const char *format, ...)
                                __attribute__ ((format (printf, 1, 2)));

// cannot use __attribute__(format) for errorf as we add %w handling.
// still `const char *` overload is useful for performance.
LIBGOLANG_API error ___errorf(const char *format, ...);
LIBGOLANG_API error ___errorfTryWrap(const char *format, error last_err, ...);

// _errorf(..., err) tails here.
template<typename ...Headv>
inline error __errorf(std::true_type, const char *format, error last_err, Headv... headv) {
    return ___errorfTryWrap(format, last_err, headv..., ___error_str(last_err).c_str());
}

// _errorf(..., !err) tails here.
template<typename ...Headv, typename Last>
inline error __errorf(std::false_type, const char *format, Last last, Headv... headv) {
    return ___errorf(format, headv..., last);
}

template<typename ...Argv, int ...HeadIdxv>
inline error _errorf(intseq<HeadIdxv...>, const char *format, Argv... argv) {
    auto argt = std::make_tuple(argv...);
    auto last = std::get<sizeof...(argv)-1>(argt);
    return __errorf(std::is_same<decltype(last), error>(), format, last, std::get<HeadIdxv>(argt)...);
}

inline error errorf(const char *format) {
    return ___errorf(format);
}
template<typename ...Argv>
inline error errorf(const char *format, Argv... argv) {
    return _errorf(typename intrange<sizeof...(argv)-1>::type(), format, argv...);
}

}}  // golang::fmt::

#endif  // _NXD_LIBGOLANG_FMT_H
