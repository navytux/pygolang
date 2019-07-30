# Copyright (C) 2018-2019  Nexedi SA and Contributors.
#                          Kirill Smelkov <kirr@nexedi.com>
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

import os, os.path
from golang._gopath import gimport
import pytest

# tgopath sets GOPATH to testdata/src during test execution.
@pytest.fixture
def tgopath():
    gopath = os.environ.get('GOPATH')
    os.environ['GOPATH'] = '%s/testdata' % (os.path.dirname(__file__),)
    yield
    if gopath is None:
        del os.environ['GOPATH']
    else:
        os.environ['GOPATH'] = gopath


def test_import_module(tgopath):
    hello = gimport('lab.nexedi.com/kirr/hello')
    assert hello.TAG == 'gopath: test: hello.py'
    hello.TAG = 'loaded'

    # verify second gimport does not reload
    hello2 = gimport('lab.nexedi.com/kirr/hello')
    assert hello2 is hello

    # even though hello2 is hello - the module could be reloaded.
    # check it is not the case via .TAG .
    assert hello.TAG == 'loaded', 'module was reloaded'


def test_import_package(tgopath):
    world = gimport('lab.nexedi.com/kirr/world')
    assert world.TAG == 'gopath: test: world/__init__.py'
    world.TAG = 'loaded'

    # verify second gimport does not reload
    world2 = gimport('lab.nexedi.com/kirr/world')
    assert world2 is world

    # even though world2 is world - the module could be reloaded.
    # check it is not the case via .TAG .
    assert world.TAG =='loaded', 'module was reloaded'
