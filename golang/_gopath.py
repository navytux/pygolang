# Copyright (C) 2018-2024  Nexedi SA and Contributors.
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
"""Module _gopath provides way to import python modules by full path in a Go workspace.

For example

    lonet = gopath.gimport('lab.nexedi.com/kirr/go123/xnet/lonet')

will import either

    lab.nexedi.com/kirr/go123/xnet/lonet.py, or
    lab.nexedi.com/kirr/go123/xnet/lonet/__init__.py

located in src/ under $GOPATH.
"""

from __future__ import print_function, absolute_import

import os, os.path
import sys
import six

# _gopathv returns $GOPATH vector.
def _gopathv():
    gopath = os.environ.get('GOPATH')
    if gopath is None:
        # since Go1.8 default GOPATH is ~/go
        gopath = os.path.expanduser(os.path.join('~', 'go'))
    return gopath.split(os.path.pathsep)


# gimport imports python module or package from fully-qualified module name under $GOPATH.
def gimport(name):
    _gimport_lock()
    try:
        return _gimport(name)
    finally:
        _gimport_unlock()

# on py2 there is global import lock
# on py3 we need to organize our own gimport synchronization
if six.PY2:
    import imp
    _gimport_lock   = imp.acquire_lock
    _gimport_unlock = imp.release_lock
else:
    from importlib import machinery as imp_machinery
    from importlib import util      as imp_util
    from golang import sync
    _gimport_mu = sync.Mutex()
    _gimport_lock   = _gimport_mu.lock
    _gimport_unlock = _gimport_mu.unlock

def _gimport(name):
    # we will register imported module into sys.modules with adjusted path.
    # reason: if we leave dots in place, python emits warning:
    #   RuntimeWarning: Parent module 'lab.nexedi' not found while handling absolute import
    #
    # we put every imported module under `golang._gopath.` namespace with '.' changed to '_'
    modname = 'golang._gopath.' + name.replace('.', '_')

    try:
        return sys.modules[modname]
    except KeyError:
        # not yet imported
        pass

    # search for module in every GOPATH entry
    modpath = None
    gopathv = _gopathv()
    for g in gopathv:
        # module: .../name.py
        modpath = os.path.join(g, 'src', name + '.py')
        if os.path.exists(modpath):
            break

        # package: .../name/__init__.py
        modpath = os.path.join(g, 'src', name, '__init__.py')
        if os.path.exists(modpath):
            break

    else:
        modpath = None

    if modpath is None:
        raise ImportError('gopath: no module named %s' % name)


    # https://stackoverflow.com/a/67692
    return _imp_load_source(modname, modpath)

def _imp_load_source(modname, modpath):
    if six.PY2:
        return imp.load_source(modname, modpath)

    # https://docs.python.org/3/whatsnew/3.12.html#imp
    loader = imp_machinery.SourceFileLoader(modname, modpath)
    spec   = imp_util.spec_from_file_location(modname, modpath, loader=loader)
    mod    = imp_util.module_from_spec(spec)
    sys.modules[modname] = mod
    loader.exec_module(mod)
    return mod
