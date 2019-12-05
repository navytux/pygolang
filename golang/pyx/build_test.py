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

testprog = dirname(__file__) + "/testprog"

# verify that we can build/run external package that uses pygolang in pyx mode.
def test_pyx_build():
    pyxuser = testprog + "/golang_pyx_user"
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


# verify that we can build/run external dso that uses libgolang.
def test_dso_build():
    dsouser = testprog + "/golang_dso_user"
    pyrun(["setup.py", "build_dso", "-i"], cwd=dsouser)
    pyrun(["setup.py", "build_ext", "-i"], cwd=dsouser)

    # run built test.
    _ = pyout(["-c",
        # XXX `import golang` is a hack - see test_pyx_build for details.
        "import golang;" +
        "from dsouser import test; test.main()"], cwd=dsouser)
    assert _ == b"dso.cpp: OK\n"


# verify that custom classes can be used via cmdclass
def test_pyx_build_cmdclass():
    _ = pyout(["cmdclass_custom.py", "build_ext"], cwd=testprog)
    assert b"pyx.build:RUN_BUILD_EXT" in _
