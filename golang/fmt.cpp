// Copyright (C) 2019  Nexedi SA and Contributors.
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

// Package fmt mirrors Go package fmt.
// See fmt.h for package overview.

// TODO consider reusing https://github.com/fmtlib/fmt

#include "golang/fmt.h"
#include "golang/errors.h"

#include <stdarg.h>
#include <stdio.h>


// golang::fmt::
namespace golang {
namespace fmt {

static
string _vsprintf(const char *format, va_list argp) {
    // based on https://stackoverflow.com/a/26221725/9456786
    va_list argp2;
    va_copy(argp2, argp);
    size_t nchar = ::vsnprintf(NULL, 0, format, argp2);
    va_end(argp2);

    std::unique_ptr<char[]> buf( new char[nchar /*for \0*/+1] );
    vsnprintf(buf.get(), /*size limit in bytes including \0*/nchar+1, format, argp);
    return string(buf.get(), buf.get() + nchar); // without trailing '\0'
}

string sprintf(const string &format, ...) {
    va_list argp;
    va_start(argp, format);
    string str = fmt::_vsprintf(format.c_str(), argp);
    va_end(argp);
    return str;
}

string sprintf(const char *format, ...) {
    va_list argp;
    va_start(argp, format);
    string str = fmt::_vsprintf(format, argp);
    va_end(argp);
    return str;
}

error errorf(const string &format, ...) {
    va_list argp;
    va_start(argp, format);
    error err = errors::New(fmt::_vsprintf(format.c_str(), argp));
    va_end(argp);
    return err;
}

error errorf(const char *format, ...) {
    va_list argp;
    va_start(argp, format);
    error err = errors::New(fmt::_vsprintf(format, argp));
    va_end(argp);
    return err;
}

}}  // golang::fmt::
