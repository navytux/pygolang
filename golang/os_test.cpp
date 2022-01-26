// Copyright (C) 2021-2022  Nexedi SA and Contributors.
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

#include "golang/io.h"
#include "golang/os.h"
#include "golang/_testing.h"
using namespace golang;
using std::tie;


void __test_os_fileio_cpp(const string& tmpd) {
    string tpath = tmpd + "/1";

    os::File f;
    error    err;

    // open !existing
    tie(f, err) = os::Open(tpath);
    ASSERT(f == nil);
    ASSERT(err != nil);
    ASSERT_EQ(err->Error(), "open " + tpath + ": No such file or directory");

    // open +w
    tie(f, err) = os::Open(tpath, O_CREAT | O_RDWR);
    ASSERT(f != nil);
    ASSERT(err == nil);

    // write
    int n;
    tie(n, err) = f->Write("hello world\n", 12);
    ASSERT_EQ(n, 12);
    ASSERT(err == nil);

    // close
    err = f->Close();
    ASSERT(err == nil);
    err = f->Close();
    ASSERT(err != nil);
    ASSERT_EQ(err->Error(), "close " + tpath + ": file already closed");

    // read
    tie(f, err) = os::Open(tpath);
    ASSERT(f != nil);
    ASSERT(err == nil);

    char buf[128], *p=buf;
    int count=20, got=0;

    while (got < 12) {
        tie(n, err) = f->Read(p, count);
        ASSERT(err == nil);
        ASSERT(n > 0);
        ASSERT(n <= count);
        p += n;
        got += n;
        count -= n;
    }

    ASSERT_EQ(got, 12);
    ASSERT_EQ(string(buf, got), "hello world\n");

    tie(n, err) = f->Read(buf, 10);
    ASSERT_EQ(n, 0);
    ASSERT_EQ(err, io::EOF_);

    // fstat
    struct stat st;
    err = f->Stat(&st);
    ASSERT(err == nil);
    ASSERT_EQ(st.st_size, 12);

    err = f->Close();
    ASSERT(err == nil);

    // readfile
    string data;
    tie(data, err) = os::ReadFile(tpath);
    ASSERT(err == nil);
    ASSERT_EQ(data, "hello world\n");
}

void _test_os_pipe_cpp() {
    os::File r1, w2; // r1 <- w2
    os::File r2, w1; // w1 -> r2
    error    err;

    tie(r1, w2, err) = os::Pipe();
    ASSERT(r1 != nil);
    ASSERT(w2 != nil);
    ASSERT(err == nil);

    tie(r2, w1, err) = os::Pipe();
    ASSERT(r2 != nil);
    ASSERT(w1 != nil);
    ASSERT(err == nil);


    // T2: ->r2->w2 echo
    go([r2,w2]() {
        char buf[32];
        error err;

        while (1) {
            int n, n2;
            tie(n, err) = r2->Read(buf, sizeof(buf));
            if (err == io::EOF_)
                break;

            ASSERT(err == nil);
            ASSERT(0 < n && n <= sizeof(buf));

            tie(n2, err) = w2->Write(buf, n);
            ASSERT(err == nil);
            ASSERT_EQ(n2, n);
        }

        err = r2->Close(); ASSERT(err == nil);
        err = w2->Close(); ASSERT(err == nil);
    });

    // T1: send 1, 2, 3, ... to T2 and assert the numbers come back
    int n;
    char buf[32];
    for (char c = 0; c < 100; ++c) {
        buf[0] = c;
        tie(n, err) = w1->Write(buf, 1);
        ASSERT(err == nil);
        ASSERT_EQ(n, 1);

        buf[0] = -1;
        tie(n, err) = r1->Read(buf, sizeof(buf));
        ASSERT(err == nil);
        ASSERT_EQ(n, 1);
        ASSERT_EQ(buf[0], c);
    }

    err = w1->Close(); ASSERT(err == nil);
    tie(n, err) = r1->Read(buf, sizeof(buf));
    ASSERT_EQ(n, 0);
    ASSERT_EQ(err, io::EOF_);

    err = r1->Close(); ASSERT(err == nil);
}
