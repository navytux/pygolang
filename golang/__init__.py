# -*- coding: utf-8 -*-
# Copyright (C) 2018-2020  Nexedi SA and Contributors.
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
- `error` and package `errors` provide error chaining.
- `b` and `u` provide way to make sure an object is either bytes or unicode.
- `gimport` allows to import python modules by full path in a Go workspace.

See README for thorough overview.
See also package golang.pyx which provides similar functionality for Cython nogil.
"""

from __future__ import print_function, absolute_import

__version__ = "0.0.9"

__all__ = ['go', 'chan', 'select', 'default', 'nilchan', 'defer', 'panic',
           'recover', 'func', 'error', 'b', 'u', 'gimport']

from golang._gopath import gimport  # make gimport available from golang
import inspect, sys
import decorator, six

from golang._golang import _pysys_exc_clear as _sys_exc_clear

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

        # py2: to-be next exception in exception chain (PEP 3134)
        if six.PY2:
            self.exc_ctx    = None  # exception context to chain new exception into
            self.exc_ctx_tb = None  # exc_tb we got when catching .exc_ctx.
                                    # we will set .exc_ctx.__traceback__ to this
                                    # if/when .exc_ctx will be chained into.
    def __enter__(self):
        pass

    # __exit__ simulates both except and finally.
    def __exit__(__goframe__, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            __goframe__.recovered = False

        # py2: simulate exception chaining (PEP 3134)
        if six.PY2:
            if exc_val is not None:
                # exc_val is current outer exception raised by e.g. earlier
                # defers; it can be itself chained.
                # .exc_ctx is current inner exception we saved before calling
                # code that raised exc_val. For example:
                #
                #   _GoFrame.__exit__:
                #       saves .exc_ctx      # .exc_ctx = A1
                #       with __goframe__:
                #           call other defer from .deferv
                #       __exit__(exc_val):  # exc_val = B3 (-> linked to B2 -> B1)
                #
                # the order in which exceptions were raised is: A1 B1 B2 B3
                # thus A1 is the context of B1, or in other words, .exc_ctx
                # should be linked to from tail of exc_val exception chain.
                exc_tail = exc_val
                while 1:
                    _ = getattr(exc_tail, '__context__', None)
                    if _ is None:
                        break
                    exc_tail = _
                exc_tail.__context__ = __goframe__.exc_ctx

                # make sure .__cause__ and .__suppress_context__ are always present
                if not hasattr(exc_val, '__cause__'):
                    exc_val.__cause__     = None
                if not hasattr(exc_val, '__suppress_context__'):
                    exc_val.__suppress_context__ = False

                # set .__traceback__ only for chained-to exceptions. top-level
                # raised exception must remain without __traceback__, because
                # if it was not yet caught, setting __traceback__ here early
                # will be wrong compared to what sys.exc_info() returns in
                # caller except block.
                if __goframe__.exc_ctx is not None:
                    __goframe__.exc_ctx.__traceback__ = __goframe__.exc_ctx_tb
                __goframe__.exc_ctx    = exc_val
                __goframe__.exc_ctx_tb = exc_tb

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

    _, exc, exc_tb = sys.exc_info()
    if exc is not None:
        goframe.recovered = True
        # recovered: clear current exception context
        _sys_exc_clear()
        if six.PY2:
            goframe.exc_ctx    = None
            goframe.exc_ctx_tb = None

            # the exception is caught. Now is the correct time to set its .__traceback__
            #
            # we don't need to set .__context__ and the like here - _GoFrame.__exit__
            # makes sure to add those attributes to any exception recover might catch -
            # because hereby part of recover is always run under defer.
            exc.__traceback__ = exc_tb

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


# py2: defer simulates exception chaining. Adjust traceback.print_exception()
# and default sys.excepthook so that, out of the box, dump of chained exceptions
# is printed with all details automatically.
if six.PY2:
    import traceback
    _tb_print_exception = traceback.print_exception
    def _print_exception(etype, value, tb, limit=None, file=None):
        if file is None:
            file = sys.stderr
        def emitf(msg):
            print(msg, file=file)
        def recursef(etype, value, tb):
            _print_exception(etype, value, tb, limit, file)

        _emit_exc_context(value, emitf, recursef)
        _tb_print_exception(etype, value, tb, limit, file)

    _tb_format_exception = traceback.format_exception
    def _format_exception(etype, value, tb, limit=None):
        l = []
        def emitf(msg):
            l.append(msg+"\n")
        def recursef(etype, value, tb):
            l.extend(_format_exception(etype, value, tb, limit))

        _emit_exc_context(value, emitf, recursef)
        l += _tb_format_exception(etype, value, tb, limit)
        return l

    # _emit_exc_context emits traceback for exc cause/context if any.
    #
    # emitf is used to emit raw text.
    # recursef is used to spawn processing on cause exception object.
    def _emit_exc_context(exc, emitf, recursef):
        ecause   = getattr(exc, '__cause__', None)
        econtext = getattr(exc, '__context__', None)
        if ecause is not None:
            recursef(type(ecause), ecause, getattr(ecause, '__traceback__', None))
            emitf("\nThe above exception was the direct cause of the following exception:\n")

        elif econtext is not None and not getattr(exc, '__suppress_context__', False):
            recursef(type(econtext), econtext, getattr(econtext, '__traceback__', None))
            emitf("\nDuring handling of the above exception, another exception occurred:\n")

    # patch traceback functions: in python2.7 all exception-related functions
    # in traceback module use either tb.print_exception() or tb.format_exception().
    # This way if we patch those two and someone uses e.g. tb.print_exc(),
    # it will print exception with cause/context included.
    traceback.print_exception  = _print_exception
    traceback.format_exception = _format_exception

    # adjust default sys.excepthook. Do this only if sys.excepthook was not already overridden.
    # Two cases are possible here:
    #   1) golang is imported in regular interpreter, possibly late in the process;
    #   2) golang is imported early as part of gpython startup.
    # For "2" when we get here the "pristine" precondition will be true, and so
    # we'll get to adjust sys.excepthook . For "1" if sys.excepthook is
    # pristine - it is safe to adjust. If sys.excepthook is not pristine - it
    # is not safe to adjust, because e.g. `import golang` was run from an
    # interactive IPython session and IPython already installed its own
    # sys.excepthook. We don't adjust sys.excepthook in such case, but we also
    # provide integration patches that add exception chaining support for
    # traceback dump functionality in popular third-party software.
    if sys.excepthook is sys.__excepthook__:
        sys.excepthook = traceback.print_exception

    # install pytest/ipython integration patches.
    # each patch is activated only when/if corresponding software is imported and actually used.
    import golang._patch.pytest_py2
    import golang._patch.ipython_py2


# ---- go + channels, panic, error, etc... ----

from ._golang import    \
    pygo        as go,      \
    pychan      as chan,    \
    pyselect    as select,  \
    pydefault   as default, \
    pynilchan   as nilchan, \
    _PanicError,            \
    pypanic     as panic,   \
    pyerror     as error,   \
    pyb         as b,       \
    pyu         as u
