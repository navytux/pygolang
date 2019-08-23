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

from golang.golang_test import pyrun, pyout
from os.path import dirname

# verify that we can build/run external package that uses pygolang in pyx mode.
def test_pyx_build():
    pyxuser = dirname(__file__) + "/testprog/golang_pyx_user"
    pyrun(["setup.py", "build_ext", "-i"], cwd=pyxuser)

    # run built test.
    _ = pyout(["-c",
        # XXX `import golang` is a hack: it dynamically loads _golang.so -> libgolang.so,
        # and this way dynamic linker already has libgolang.so DSO found and in
        # memory for all further imports. If we don't, current state of setuptools_dso
        # is that `import pyxuser.test` will fail finding libgolang.so.
        "import golang;" +
        "from pyxuser import test; test.main()"], cwd=pyxuser)
    assert _ == b"test.pyx: OK\n"
