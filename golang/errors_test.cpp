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

#include "golang/errors.h"

#include "golang/_testing.h"
using namespace golang;

void _test_errors_new_cpp() {
    error err = errors::New("hello world");
    ASSERT_EQ(err->Error(), "hello world");
}

struct _MyError final : _error, object {
    string msg;
    string Error() {
        return msg;
    }
    _MyError(const string& msg) : msg(msg) {}
    ~_MyError() {}

    void incref() { object::incref(); }
    void decref() {
        if (object::__decref())
            delete this;
    }
};

struct _MyWrapError final : _errorWrapper, object {
    string subj;
    error  err;
    string Error() {
        return subj + ": " + err->Error();
    }
    error Unwrap() {
        return err;
    }

    _MyWrapError(string subj, error err) : subj(subj), err(err) {}
    ~_MyWrapError() {}

    void incref() { object::incref(); }
    void decref() {
        if (object::__decref())
            delete this;
    }
};

typedef refptr<_MyError> MyError;

void _test_errors_unwrap_cpp() {
    error err1, err2;
    ASSERT_EQ(errors::Unwrap(/*nil*/error()), /*nil*/error());

    err1 = adoptref(static_cast<_error*>(new _MyError("zzz")));
    ASSERT_EQ(errors::Unwrap(err1), /*nil*/error());

    _MyWrapError* _err2 = new _MyWrapError("aaa", err1);
    err2 = adoptref(static_cast<_error*>(_err2));
    ASSERT_EQ(errors::Unwrap(err2), err1);

    // test err2.Unwrap() returning nil
    _err2->err = nil;
    ASSERT_EQ(_err2->Unwrap(), /*nil*/error());
    ASSERT_EQ(errors::Unwrap(err2), /*nil*/error());
}

void _test_errors_is_cpp() {
    auto E = errors::New;
    ASSERT_EQ(errors::Is(/*nil*/error(),    /*nil*/error()),    true);
    ASSERT_EQ(errors::Is(E("a"),            /*nil*/error()),    false);
    ASSERT_EQ(errors::Is(/*nil*/error(),    E("b")),            false);

    auto W = [](string subj, error err) -> error {
        return adoptref(static_cast<_error*>(new _MyWrapError(subj, err)));
    };

    error ewrap = W("hello", W("world", E("мир")));
    ASSERT_EQ(errors::Is(ewrap, E("мир")),    true);
    ASSERT_EQ(errors::Is(ewrap, E("май")),    false);

    ASSERT_EQ(errors::Is(ewrap, W("world", E("мир"))),  true);
    ASSERT_EQ(errors::Is(ewrap, W("hello", E("мир"))),  false);
    ASSERT_EQ(errors::Is(ewrap, W("hello", E("май"))),  false);
    ASSERT_EQ(errors::Is(ewrap, W("world", E("май"))),  false);

    ASSERT_EQ(errors::Is(ewrap, W("hello", W("world", E("мир")))),  true);
    ASSERT_EQ(errors::Is(ewrap, W("a",     W("world", E("мир")))),  false);
    ASSERT_EQ(errors::Is(ewrap, W("hello", W("b",     E("мир")))),  false);
    ASSERT_EQ(errors::Is(ewrap, W("hello", W("world", E("c")))),    false);

    ASSERT_EQ(errors::Is(ewrap, W("x", W("hello", W("world", E("мир"))))),  false);
}
