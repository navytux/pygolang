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

#include "golang/strings.h"
#include <vector>

#include "golang/_testing.h"
using namespace golang;
using std::vector;

void _test_strings_has_prefix() {
    ASSERT(strings::has_prefix("", "")          == true);
    ASSERT(strings::has_prefix("", "a")         == false);
    ASSERT(strings::has_prefix("", 'a')         == false);
    ASSERT(strings::has_prefix("b", "a")        == false);
    ASSERT(strings::has_prefix("b", 'a')        == false);
    ASSERT(strings::has_prefix("a", "a")        == true);
    ASSERT(strings::has_prefix("a", 'a')        == true);
    ASSERT(strings::has_prefix("a", "aa")       == false);
    ASSERT(strings::has_prefix("hello", "")     == true);
    ASSERT(strings::has_prefix("hello", "h")    == true);
    ASSERT(strings::has_prefix("hello", 'h')    == true);
    ASSERT(strings::has_prefix("hello", 'X')    == false);
    ASSERT(strings::has_prefix("hello", "he")   == true);
    ASSERT(strings::has_prefix("hello", "hel")  == true);
    ASSERT(strings::has_prefix("hello", "hez")  == false);
    ASSERT(strings::has_prefix("hello", "a")    == false);
}

void _test_strings_trim_prefix() {
    ASSERT_EQ(strings::trim_prefix("", "")              , "");
    ASSERT_EQ(strings::trim_prefix("", "a")             , "");
    ASSERT_EQ(strings::trim_prefix("", 'a')             , "");
    ASSERT_EQ(strings::trim_prefix("a", "")             , "a");
    ASSERT_EQ(strings::trim_prefix("a", "b")            , "a");
    ASSERT_EQ(strings::trim_prefix("a", 'b')            , "a");
    ASSERT_EQ(strings::trim_prefix("a", "a")            , "");
    ASSERT_EQ(strings::trim_prefix("a", 'a')            , "");
    ASSERT_EQ(strings::trim_prefix("a", "ab")           , "a");
    ASSERT_EQ(strings::trim_prefix("hello", "world")    , "hello");
    ASSERT_EQ(strings::trim_prefix("hello", "h")        , "ello");
    ASSERT_EQ(strings::trim_prefix("hello", 'h')        , "ello");
    ASSERT_EQ(strings::trim_prefix("hello", "he")       , "llo");
    ASSERT_EQ(strings::trim_prefix("hello", "hel")      , "lo");
    ASSERT_EQ(strings::trim_prefix("hello", "hez")      , "hello");
}

void _test_strings_has_suffix() {
    ASSERT(strings::has_suffix("", "")          == true);
    ASSERT(strings::has_suffix("", "a")         == false);
    ASSERT(strings::has_suffix("", 'a')         == false);
    ASSERT(strings::has_suffix("b", "a")        == false);
    ASSERT(strings::has_suffix("b", 'a')        == false);
    ASSERT(strings::has_suffix("a", "a")        == true);
    ASSERT(strings::has_suffix("a", 'a')        == true);
    ASSERT(strings::has_suffix("a", "aa")       == false);
    ASSERT(strings::has_suffix("hello", "")     == true);
    ASSERT(strings::has_suffix("hello", "o")    == true);
    ASSERT(strings::has_suffix("hello", 'o')    == true);
    ASSERT(strings::has_suffix("hello", 'X')    == false);
    ASSERT(strings::has_suffix("hello", "lo")   == true);
    ASSERT(strings::has_suffix("hello", "llo")  == true);
    ASSERT(strings::has_suffix("hello", "llz")  == false);
    ASSERT(strings::has_suffix("hello", "a")    == false);
}

void _test_strings_trim_suffix() {
    ASSERT_EQ(strings::trim_suffix("", "")              , "");
    ASSERT_EQ(strings::trim_suffix("", "a")             , "");
    ASSERT_EQ(strings::trim_suffix("", 'a')             , "");
    ASSERT_EQ(strings::trim_suffix("a", "")             , "a");
    ASSERT_EQ(strings::trim_suffix("a", "b")            , "a");
    ASSERT_EQ(strings::trim_suffix("a", 'b')            , "a");
    ASSERT_EQ(strings::trim_suffix("a", "a")            , "");
    ASSERT_EQ(strings::trim_suffix("a", 'a')            , "");
    ASSERT_EQ(strings::trim_suffix("a", "ab")           , "a");
    ASSERT_EQ(strings::trim_suffix("hello", "world")    , "hello");
    ASSERT_EQ(strings::trim_suffix("hello", "o")        , "hell");
    ASSERT_EQ(strings::trim_suffix("hello", 'o')        , "hell");
    ASSERT_EQ(strings::trim_suffix("hello", "lo")       , "hel");
    ASSERT_EQ(strings::trim_suffix("hello", "llo")      , "he");
    ASSERT_EQ(strings::trim_suffix("hello", "llz")      , "hello");
}

void _test_strings_split() {
    auto V = [](const std::initializer_list<string> &argv) -> vector<string> {
        return argv;
    };

    ASSERT_EQ(strings::split(""             ,  ' ')         , V({}));
    ASSERT_EQ(strings::split("a"            ,  ' ')         , V({"a"}));
    ASSERT_EQ(strings::split("a "           ,  ' ')         , V({"a", ""}));
    ASSERT_EQ(strings::split(" a"           ,  ' ')         , V({"", "a"}));
    ASSERT_EQ(strings::split("ab "          ,  ' ')         , V({"ab", ""}));
    ASSERT_EQ(strings::split("ab c"         ,  ' ')         , V({"ab", "c"}));
    ASSERT_EQ(strings::split("ab cd"        ,  ' ')         , V({"ab", "cd"}));
    ASSERT_EQ(strings::split("ab cd "       ,  ' ')         , V({"ab", "cd", ""}));
    ASSERT_EQ(strings::split("ab cd e"      ,  ' ')         , V({"ab", "cd", "e"}));
    ASSERT_EQ(strings::split(" ab cd e"     ,  ' ')         , V({"", "ab", "cd", "e"}));
    ASSERT_EQ(strings::split("  ab cd e"    ,  ' ')         , V({"", "", "ab", "cd", "e"}));
}
