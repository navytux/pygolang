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

// Package errors mirrors Go package errors.
// See errors.h for package overview.

#include "golang/errors.h"


// golang::errors::
namespace golang {
namespace errors {

// _TextError implements error with text string created by New.
struct _TextError final : _error, object {
    string _text;

    void incref() {
        object::incref();
    }
    void decref() {
        if (__decref())
            delete this;
    }
    ~_TextError() {}

    _TextError(const string& text) : _text(text) {}

    string Error() {
        return _text;
    }
};

error New(const string& text) {
    return adoptref(static_cast<_error*>(new _TextError(text)));
}


error Unwrap(error err) {
    if (err == nil)
        return nil;

    _errorWrapper* _werr = dynamic_cast<_errorWrapper*>(err._ptr());
    if (_werr == nil)
        return nil;

    return _werr->Unwrap();
}

bool Is(error err, error target) {
    if (target == nil)
        return (err == nil);

    for(;;) {
        if (err == nil)
            return false;

        if (typeid(*err) == typeid(*target))
            if (err->Error() == target->Error()) // XXX hack instead of dynamic == (not available in C++)
                return true;

        err = Unwrap(err);
    }
}

}}  // golang::errors::
