# -*- coding: utf-8 -*-
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
"""Package golang provides Go-like features for Python.

- `go` spawns lightweight thread.
- `chan` and `select` provide channels with Go semantic.
- `func` allows to define methods separate from class.
- `defer` allows to schedule a cleanup from the main control flow.
- `gimport` allows to import python modules by full path in a Go workspace.

See README for thorough overview.
See also package golang.pyx which provides similar functionality for Cython nogil.
"""

from __future__ import print_function, absolute_import

__version__ = "0.0.3"

__all__ = ['go', 'chan', 'select', 'default', 'nilchan', 'defer', 'panic', 'recover', 'func', 'gimport']

from golang._gopath import gimport  # make gimport available from golang
import inspect, sys
import decorator


# @func is a necessary decorator for functions for selected golang features to work.
#
# For example it is required by defer. Usage:
#
#   @func
#   def my_function(...):
#       ...
#
# @func can be also used to define methods separate from class, for example:
#
#   @func(MyClass)
#   def my_method(self, ...):
#       ...
def func(f):
    if inspect.isclass(f):
        fcall = inspect.currentframe().f_back   # caller's frame (where @func is used)
        return _meth(f, fcall)
    else:
        return _func(f)

# _meth serves @func(cls).
def _meth(cls, fcall):
    def deco(f):
        # wrap f with @_func, so that e.g. defer works automatically.
        f = _func(f)

        if isinstance(f, (staticmethod, classmethod)):
            func_name = f.__func__.__name__
        else:
            func_name = f.__name__
        setattr(cls, func_name, f)

        # if `@func(cls) def name` caller already has `name` set, don't override it
        missing = object()
        already = fcall.f_locals.get(func_name, missing)
        if already is not missing:
            return already

        # FIXME try to arrange so that python does not set anything on caller's
        # namespace[func_name]  (currently it sets that to implicitly returned None)

    return deco

# _func serves @func.
def _func(f):
    # @staticmethod & friends require special care:
    # unpack f first to original func and then repack back after wrapping.
    fclass = None
    if isinstance(f, (staticmethod, classmethod)):
        fclass = type(f)
        f = f.__func__

    def _(f, *argv, **kw):
        # run f under separate frame, where defer will register calls.
        __goframe__ = _GoFrame()
        with __goframe__:
            return f(*argv, **kw)

    # keep all f attributes, like __name__, __doc__, etc on _
    _ = decorator.decorate(f, _)

    # repack _ into e.g. @staticmethod if that was used on f.
    if fclass is not None:
        _ = fclass(_)

    return _

# _GoFrame serves __goframe__ that is setup by @func.
class _GoFrame:
    def __init__(self):
        self.deferv    = []     # defer registers funcs here
        self.recovered = False  # whether exception, if there was any, was recovered

    def __enter__(self):
        pass

    # __exit__ simulates both except and finally.
    def __exit__(__goframe__, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            __goframe__.recovered = False

        if len(__goframe__.deferv) != 0:
            d = __goframe__.deferv.pop()

            # even if d panics - we have to call other defers
            with __goframe__:
                d()

        return __goframe__.recovered

# recover checks whether there is exception/panic currently being raised and returns it.
#
# If it was panic - it returns the argument that was passed to panic.
# If there is other exception - it returns the exception object.
#
# If there is no exception/panic, or the panic argument was None - recover returns None.
# Recover also returns None if it was not called by a deferred function directly.
def recover():
    fcall = inspect.currentframe().f_back   # caller's frame (deferred func)
    fgo   = fcall.f_back                    # caller's parent frame defined by _GoFrame.__exit__
    try:
        goframe = fgo.f_locals['__goframe__']
    except KeyError:
        # called not under go func/defer
        return None

    _, exc, _ = sys.exc_info()
    if exc is not None:
        goframe.recovered = True
    if type(exc) is _PanicError:
        exc = exc.args[0]
    return exc

# defer registers f to be called when caller function exits.
#
# It is similar to try/finally but does not force the cleanup part to be far
# away in the end.
def defer(f):
    fcall = inspect.currentframe().f_back   # caller's frame
    fgo   = fcall.f_back                    # caller's parent frame defined by @func
    try:
        goframe = fgo.f_locals['__goframe__']
    except KeyError:
        panic("function %s uses defer, but not @func" % fcall.f_code.co_name)

    goframe.deferv.append(f)



# ---- go + channels ----

from ._golang import    \
    pygo        as go,      \
    pychan      as chan,    \
    pyselect    as select,  \
    pydefault   as default, \
    pynilchan   as nilchan, \
    _PanicError,            \
    pypanic     as panic
