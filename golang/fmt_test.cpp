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

#include "golang/fmt.h"
#include "golang/_testing.h"
using namespace golang;

void _test_fmt_sprintf_cpp() {
    // NOTE not using vargs helper, since sprintf itself uses vargs and we want
    // to test varg logic there for correctness too.
    ASSERT_EQ(fmt::sprintf("hello world")        , "hello world");
    ASSERT_EQ(fmt::sprintf("hello %d zzz", 123)  , "hello 123 zzz");
    ASSERT_EQ(fmt::sprintf("%s %s: %s", "read", "myfile", "myerror") , "read myfile: myerror");

    // with string format (not `const char *`)
    const char *myerror = "myerror";
    string f = "%s %s: %s";
    const char *myfile = "myfile";
    ASSERT_EQ(fmt::sprintf(f, "read", myfile, myerror) , "read myfile: myerror");
}

void _test_fmt_errorf_cpp() {
    ASSERT_EQ(fmt::errorf("hello world")->Error()        , "hello world");
    ASSERT_EQ(fmt::errorf("hello %d zzz", 123)->Error()  , "hello 123 zzz");
    ASSERT_EQ(fmt::errorf("%s %s: %s", "read", "myfile", "myerror")->Error() , "read myfile: myerror");

    // with string format (not `const char *`)
    const char *myerror = "myerror";
    string f = "%s %s: %s";
    const char *myfile = "myfile";
    ASSERT_EQ(fmt::errorf(f, "read", myfile, myerror)->Error() , "read myfile: myerror");
}
