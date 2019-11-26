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

// Package strings mirrors Go package strings.
// See strings.h for package overview.

#include "golang/strings.h"
using std::vector;

// golang::strings::
namespace golang {
namespace strings {

bool has_prefix(const string &s, const string &prefix) {
    return s.compare(0, prefix.size(), prefix) == 0;
}

bool has_prefix(const string &s, char prefix) {
    return (s.size() >= 1 && s[0] == prefix);
}

bool has_suffix(const string &s, const string &suffix) {
    return (s.size() >= suffix.size() &&
            s.compare(s.size() - suffix.size(), suffix.size(), suffix) == 0);
}

bool has_suffix(const string &s, char suffix) {
    return (s.size() >= 1 && s[s.size()-1] == suffix);
}

string trim_prefix(const string &s, const string &prefix) {
    if (!has_prefix(s, prefix))
        return s;
    return s.substr(prefix.size());
}

string trim_prefix(const string &s, char prefix) {
    if (!has_prefix(s, prefix))
        return s;
    return s.substr(1);
}

string trim_suffix(const string &s, const string &suffix) {
    if (!has_suffix(s, suffix))
        return s;
    return s.substr(0, s.size()-suffix.size());
}

string trim_suffix(const string &s, char suffix) {
    if (!has_suffix(s, suffix))
        return s;
    return s.substr(0, s.size()-1);
}

vector<string> split(const string &s, char sep) {
    vector<string> r;
    int psep_prev=-1;
    size_t psep;
    if (s.size() == 0)
        return r;
    while (1) {
        psep = s.find(sep, psep_prev+1);
        if (psep == string::npos) {
            r.push_back(s.substr(psep_prev+1));
            return r;
        }

        r.push_back(s.substr(psep_prev+1, psep-(psep_prev+1)));
        psep_prev = psep;
    }
}

}}  // golang::strings::
