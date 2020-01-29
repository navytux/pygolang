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
// See fmt.h for package overview.

// TODO consider reusing https://github.com/fmtlib/fmt

#include "golang/fmt.h"
#include "golang/errors.h"
#include "golang/strings.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>


// golang::fmt::
namespace golang {
namespace fmt {

static
string _vsprintf(const char *format, va_list argp) {
    // based on https://stackoverflow.com/a/26221725/9456786
    va_list argp2;
    va_copy(argp2, argp);
    size_t nchar = ::vsnprintf(nil, 0, format, argp2);
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

error ___errorf(const string &format, ...) {
    va_list argp;
    va_start(argp, format);
    error err = errors::New(fmt::_vsprintf(format.c_str(), argp));
    va_end(argp);
    return err;
}

error ___errorf(const char *format, ...) {
    va_list argp;
    va_start(argp, format);
    error err = errors::New(fmt::_vsprintf(format, argp));
    va_end(argp);
    return err;
}


// _WrapError is the error created by errorf("...: %w", err).
struct _WrapError final : _errorWrapper, object {
    string _prefix;
    error  _errSuffix;

    _WrapError(const string& prefix, error err) : _prefix(prefix), _errSuffix(err) {}
    error  Unwrap() { return _errSuffix; }
    string Error() {
        return _prefix + ": " +
               (_errSuffix != nil ? _errSuffix->Error() : "%!w(<nil>)");
    }

    void incref() {
        object::incref();
    }
    void decref() {
        if (__decref())
            delete this;
    }
    ~_WrapError() {}
};

// ___errorfTryWrap serves __errorf(format, last_err, ...headv)
//
// NOTE it is called with ... = original argv with last err converted to
// err->Error().c_str() so that `errorf("... %s", ..., err)` also works.
error ___errorfTryWrap(const string& format, error last_err, ...) {
    error err;
    va_list argp;
    va_start(argp, last_err);

    if (strings::has_suffix(format, ": %w")) {
        err = adoptref(static_cast<_error*>(
                    new _WrapError(
                        fmt::_vsprintf(strings::trim_suffix(format, ": %w").c_str(), argp),
                        last_err)));
    }
    else {
        err = errors::New(fmt::_vsprintf(format.c_str(), argp));
    }

    va_end(argp);
    return err;
}

error ___errorfTryWrap(const char *format, error last_err, ...) {
    error err;
    va_list argp;
    va_start(argp, last_err);

    const char *colon = strrchr(format, ':');
    if (colon != NULL && strcmp(colon, ": %w") == 0) {
        err = adoptref(static_cast<_error*>(
                    new _WrapError(
                        // TODO try to avoid std::string
                        fmt::_vsprintf(strings::trim_suffix(format, ": %w").c_str(), argp),
                        last_err)));
    }
    else {
        err = errors::New(fmt::_vsprintf(format, argp));
    }

    va_end(argp);
    return err;
}


// ___error_str is used by errorf to convert last_err into string for not %w.
//
// if we do not take nil into account the code crashes on nil->Error() call,
// which is unreasonable, because both Go and C printf family print something
// for nil instead of crash.
//
// string - not `const char*` - is returned, because returning
// err->Error().c_str() would be not correct as error string might be destructed
// at function exit, while if we return string, that would be correct and the
// caller can use returned data without crashing.
//
// we don't return %!s(<nil>) since we don't know whether %s was used in format
// tail or not.
string ___error_str(error err) {
    return (err != nil ? err->Error() : "(<nil>)");
}


}}  // golang::fmt::
