# -*- coding: utf-8 -*-
# Copyright (C) 2019  Nexedi SA and Contributors.
#                     Kirill Smelkov <kirr@nexedi.com>
#
# This program is free software: you can Use, Study, Modify and Redistribute
# it under the terms of the GNU General Public License version 3, or (at your
# option) any later version, as published by the Free Software Foundation.
#
# You can also Link and Combine this program with other software covered by
# the terms of any of the Free Software licenses or any of the Open Source
# Initiative approved licenses and Convey the resulting work. Corresponding
# source of such a combination shall include the source code for all other
# software used.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# See COPYING file for full licensing terms.
# See https://www.nexedi.com/licensing for rationale and options.

from __future__ import print_function, absolute_import

"""
from golang.x.perf import benchlib
from os.path import dirname
import io

def ureadfile(path):
    with io.open(path, 'r', encoding='utf-8') as f:
        return f.read()

# FIXME currently fails
def _test_benchstat():
    # XXX move data back inline to here?
    B, _ = benchlib.load_file("%s/testdata/1" % dirname(__file__))
    ok   = ureadfile("%s/testdata/1.benchstat" % dirname(__file__))
    for b in B:
        print(b)

    #fout = io.TextIOWrapper(io.BytesIO(), encoding='utf-8')
    fout = io.TextIOWrapper(io.StringIO(), encoding='utf-8')
    #fout = io.BytesIO()
    benchlib.benchstat(fout, B)

    # FIXME it prints everything with unit=s/op and for seconds
    print()
    print(fout.getvalue())

    assert fout.getvalue() == ok
"""
