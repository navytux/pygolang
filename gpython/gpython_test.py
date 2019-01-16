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

import sys, os, golang, subprocess
from six import PY2, PY3
from six.moves import builtins
import pytest

# @gpython_only is marker to run a test only under gpython
gpython_only = pytest.mark.skipif('GPython' not in sys.version, reason="gpython-only test")


@gpython_only
def test_defaultencoding_utf8():
    assert sys.getdefaultencoding() == 'utf-8'

@gpython_only
def test_golang_builtins():
    # some direct accesses
    assert go     is golang.go
    assert chan   is golang.chan
    assert select is golang.select

    # indirectly verify golang.__all__
    for k in golang.__all__:
        assert getattr(builtins, k) is getattr(golang, k)

@gpython_only
def test_gevent_activated():
    from gevent.monkey import is_module_patched as patched, is_object_patched as obj_patched

    # builtin (gevent: only on py2 - on py3 __import__ uses fine-grained locking)
    if PY2:
        assert obj_patched('__builtin__', '__import__')

    assert patched('socket')
    # patch_socket(dns=True) also patches vvv
    assert obj_patched('socket', 'getaddrinfo')
    assert obj_patched('socket', 'gethostbyname')
    # ...

    assert patched('time')

    assert patched('select')
    import select as select_mod # patch_select(aggressive=True) removes vvv
    assert not hasattr(select_mod, 'epoll')
    assert not hasattr(select_mod, 'kqueue')
    assert not hasattr(select_mod, 'kevent')
    assert not hasattr(select_mod, 'devpoll')

    # XXX on native windows, patch_{os,signal} do nothing currently
    if os.name != 'nt':
        assert patched('os')
        assert patched('signal')

    assert patched('thread' if PY2 else '_thread')
    assert patched('threading')
    assert patched('_threading_local')

    assert patched('ssl')
    assert patched('subprocess')
    #assert patched('sys')       # currently disabled

    if sys.hexversion >= 0x03070000: # >= 3.7.0
        assert patched('queue')

@gpython_only
def test_executable():
    # sys.executable must point to gpython and we must be able to execute it.
    assert 'gpython' in sys.executable
    out = subprocess.check_output([sys.executable, '-c', 'import sys; print(sys.version)'])
    assert ('[GPython %s]' % golang.__version__) in str(out)

# TODO test_pymain (it is not gpython_only)
