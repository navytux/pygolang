# cython: language_level=2
# Copyright (C) 2019-2020  Nexedi SA and Contributors.
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
"""_sync.pyx implements sync.pyx - see _sync.pxd for package overview."""

from __future__ import print_function, absolute_import

from cython  cimport final
from cpython cimport PyObject, PY_MAJOR_VERSION
from golang  cimport nil, newref, topyexc
from golang  cimport context
from golang.pyx cimport runtime
ctypedef runtime._PyError* runtime_pPyError # https://github.com/cython/cython/issues/534

# internal API sync.h exposes only to sync.pyx
cdef extern from "golang/sync.h" namespace "golang::sync" nogil:
    context.Context _WorkGroup_ctx(_WorkGroup *_wg)

from libcpp.cast cimport dynamic_cast

import sys as pysys


@final
cdef class PySema:
    cdef Sema sema

    # FIXME cannot catch/pyreraise panic of .sema ctor
    # https://github.com/cython/cython/issues/3165

    def acquire(PySema pysema):
        with nogil:
            semaacquire_pyexc(&pysema.sema)

    def release(PySema pysema):
        semarelease_pyexc(&pysema.sema)

    # with support
    __enter__ = acquire
    def __exit__(pysema, exc_typ, exc_val, exc_tb):
        pysema.release()

@final
cdef class PyMutex:
    cdef Mutex mu

    # FIXME cannot catch/pyreraise panic of .mu ctor
    # https://github.com/cython/cython/issues/3165

    def lock(PyMutex pymu):
        with nogil:
            mutexlock_pyexc(&pymu.mu)

    def unlock(PyMutex pymu):
        mutexunlock_pyexc(&pymu.mu)


    # with support
    __enter__ = lock
    def __exit__(PyMutex pymu, exc_typ, exc_val, exc_tb):
        pymu.unlock()


@final
cdef class PyRWMutex:
    cdef RWMutex mu

    # FIXME cannot catch/pyreraise panic of .mu ctor
    # https://github.com/cython/cython/issues/3165

    def Lock(PyRWMutex pymu):
        with nogil:
            rwmutex_lock_pyexc(&pymu.mu)

    def Unlock(PyRWMutex pymu):
        # NOTE nogil needed for unlock since RWMutex _locks_ internal mu even in unlock
        with nogil:
            rwmutex_unlock_pyexc(&pymu.mu)

    def RLock(PyRWMutex pymu):
        with nogil:
            rwmutex_rlock_pyexc(&pymu.mu)

    def RUnlock(PyRWMutex pymu):
        # NOTE nogil needed for runlock (see ^^^)
        with nogil:
            rwmutex_runlock_pyexc(&pymu.mu)

    def UnlockToRLock(PyRWMutex pymu):
        # NOTE nogil needed (see ^^^)
        with nogil:
            rwmutex_unlocktorlock_pyexc(&pymu.mu)

    # with support (write by default)
    __enter__ = Lock
    def __exit__(PyRWMutex pymu, exc_typ, exc_val, exc_tb):
        pymu.Unlock()

    # TODO .RLocker() that returns X : X.Lock() -> .RLock() and for unlock correspondingly ?
    # TODO then `with mu.RLocker()` would mean "with read lock".


@final
cdef class PyOnce:
    """Once allows to execute an action only once.

    For example:

      once = Once()
      ...
      once.do(doSomething)
    """
    cdef Once once

    # FIXME cannot catch/pyreraise panic of .once ctor
    # https://github.com/cython/cython/issues/3165

    def do(PyOnce pyonce, object f):
        with nogil:
            _once_pydo(&pyonce.once, <PyObject *>f)

cdef void _once_pydo(Once *once, PyObject *f) nogil except *:
    __once_pydo(once, f)

cdef extern from * nogil:
    """
    static void __pyx_f_6golang_5_sync__pycall_fromnogil(PyObject *);
    static void __once_pydo(golang::sync::Once *once, PyObject *f) {
        once->do_([&]() {
            __pyx_f_6golang_5_sync__pycall_fromnogil(f);
        });
    }
    """
    void __once_pydo(Once *once, PyObject *f) except +topyexc

cdef void _pycall_fromnogil(PyObject *f) nogil except *:
    with gil:
        (<object>f)()


@final
cdef class PyWaitGroup:
    """WaitGroup allows to wait for collection of tasks to finish."""
    cdef WaitGroup wg

    # FIXME cannot catch/pyreraise panic of .wg ctor
    # https://github.com/cython/cython/issues/3165

    def done(PyWaitGroup pywg):
        with nogil:
            waitgroup_done_pyexc(&pywg.wg)

    def add(PyWaitGroup pywg, int delta):
        with nogil:
            waitgroup_add_pyexc(&pywg.wg, delta)

    def wait(PyWaitGroup pywg):
        with nogil:
            waitgroup_wait_pyexc(&pywg.wg)


@final
cdef class PyWorkGroup:
    """WorkGroup is a group of goroutines working on a common task.

    Use .go() to spawn goroutines, and .wait() to wait for all of them to
    complete, for example:

      wg = WorkGroup(ctx)
      wg.go(f1)
      wg.go(f2)
      wg.wait()

    Every spawned function accepts context related to the whole work and derived
    from ctx used to initialize WorkGroup, for example:

      def f1(ctx):
          ...

    Whenever a function returns error (raises exception), the work context is
    canceled indicating to other spawned goroutines that they have to cancel their
    work. .wait() waits for all spawned goroutines to complete and returns/raises
    error, if any, from the first failed subtask.

    WorkGroup can be also used via `with` statement where .wait() is
    automatically called at the end of the block, for example:

      with WorkGroup(ctx) as wg:
          wg.go(f1)
          wg.go(f2)

    WorkGroup is modelled after https://godoc.org/golang.org/x/sync/errgroup but
    is not equal to it.
    """
    cdef WorkGroup         wg
    cdef context.PyContext _pyctx   # PyContext wrapping wg._ctx

    def __init__(PyWorkGroup pywg, context.PyContext pyctx):
        with nogil:
            pywg.wg = workgroup_new_pyexc(pyctx.ctx)
        pywg._pyctx = context.PyContext.from_ctx(_WorkGroup_ctx(pywg.wg._ptr()))

    def __dealloc__(PyWorkGroup pywg):
        pywg.wg = nil

    def go(PyWorkGroup pywg, f, *argv, **kw):
        # run f(._pyctx, ...) via _PyCtxFunc whose operator()(ctx)
        # verifies that ctx == ._pyctx.ctx and tails to pyrunf().
        def pyrunf():
            f(pywg._pyctx, *argv, **kw)
        with nogil:
            workgroup_go_pyctxfunc_pyexc(pywg.wg, pywg._pyctx.ctx, <PyObject*>pyrunf)

    def wait(PyWorkGroup pyg):
        cdef error err
        with nogil:
            err = workgroup_wait_pyexc(pyg.wg)

        if err == nil:
            return

        # check that err is python error
        cdef runtime._PyError *_pyerr = dynamic_cast[runtime_pPyError](err._ptr())
        cdef runtime.PyError   pyerr  = newref(_pyerr)
        if pyerr == nil:
            # NOTE this also includes runtime.ErrPyStopped
            raise AssertionError("non-python error: " + err.Error())

        # reraise pyerr with original traceback
        pyerr_reraise(pyerr)

    # with support
    def __enter__(PyWorkGroup pyg):
        return pyg
    def __exit__(PyWorkGroup pyg, exc_typ, exc_val, exc_tb):
        # py2: prepare exc_val to be chained into
        if PY_MAJOR_VERSION == 2  and  exc_val is not None:
            _pyexc_contextify(exc_val, None)

        # if .wait() raises, we want raised exception to be chained into
        # exc_val via .__context__, so that
        #
        #   wg = sync.WorkGroup(ctx)
        #   defer(wg.wait)
        #   ...
        #
        # and
        #
        #   with sync.WorkGroup(ctx) as wg:
        #       ...
        #
        # are equivalent.
        #
        # Even if Python3 implements exception chaining natively, it does not
        # automatically chain exceptions in __exit__. Implement the chaining ourselves.
        try:
            pyg.wait()
        except:
            if PY_MAJOR_VERSION == 2:
                if exc_val is not None  and  not hasattr(exc_val, '__traceback__'):
                    exc_val.__traceback__ = exc_tb
            exc = pysys.exc_info()[1]
            _pyexc_contextify(exc, exc_val)
            raise

# _PyCtxFunc complements PyWorkGroup.go() : it's operator()(ctx) verifies that
# ctx is expected context and further calls python function without any arguments.
# PyWorkGroup.go() arranges to use python functions that are bound to PyContext
# corresponding to ctx.
cdef extern from * nogil:
    """
    using namespace golang;
    struct _PyCtxFunc : pyx::runtime::PyFunc {
        context::Context _ctx;  // function is bound to this context

        _PyCtxFunc(context::Context ctx, PyObject *pyf)
                : PyFunc(pyf) {
            this->_ctx = ctx;
        }

        // dtor - default is ok
        // copy - default is ok

        // WorkGroup calls f(ctx). We check that ctx is expected WorkGroup._ctx
        // and call pyf() instead (which PyWorkgroup setup to be closure to call f(pywg._pyctx)).
        error operator() (context::Context ctx) {
            if (this->_ctx != ctx)
                panic("_PyCtxFunc: called with unexpected context");
            return PyFunc::operator() ();
        }
    };
    """
    cppclass _PyCtxFunc (runtime.PyFunc):
        __init__(context.Context ctx, PyObject *pyf)
        error operator() ()



# ---- misc ----

# _pyexc_contextify makes sure pyexc has .__context__, .__cause__ and
# .__suppress_context__ attributes.
#
# .__context__ if not already present, or if it was previously None, is set to pyexccontext.
cdef _pyexc_contextify(object pyexc, pyexccontext):
    if not hasattr(pyexc, '__context__') or pyexc.__context__ is None:
        pyexc.__context__ = pyexccontext
    if not hasattr(pyexc, '__cause__'):
        pyexc.__cause__   = None
    if not hasattr(pyexc, '__suppress_context__'):
        pyexc.__suppress_context__ = False


cdef nogil:

    void semaacquire_pyexc(Sema *sema)      except +topyexc:
        sema.acquire()
    void semarelease_pyexc(Sema *sema)      except +topyexc:
        sema.release()

    void mutexlock_pyexc(Mutex *mu)         except +topyexc:
        mu.lock()
    void mutexunlock_pyexc(Mutex *mu)       except +topyexc:
        mu.unlock()

    void rwmutex_lock_pyexc(RWMutex *mu)    except +topyexc:
        mu.Lock()
    void rwmutex_unlock_pyexc(RWMutex *mu)  except +topyexc:
        mu.Unlock()
    void rwmutex_rlock_pyexc(RWMutex *mu)   except +topyexc:
        mu.RLock()
    void rwmutex_runlock_pyexc(RWMutex *mu) except +topyexc:
        mu.RUnlock()
    void rwmutex_unlocktorlock_pyexc(RWMutex *mu)   except +topyexc:
        mu.UnlockToRLock()

    void waitgroup_done_pyexc(WaitGroup *wg)                except +topyexc:
        wg.done()
    void waitgroup_add_pyexc(WaitGroup *wg, int delta)      except +topyexc:
        wg.add(delta)
    void waitgroup_wait_pyexc(WaitGroup *wg)                except +topyexc:
        wg.wait()

    WorkGroup workgroup_new_pyexc(context.Context ctx)      except +topyexc:
        return NewWorkGroup(ctx)
    void workgroup_go_pyctxfunc_pyexc(WorkGroup wg, context.Context ctx, PyObject *pyf) except +topyexc:
        wg.go(_PyCtxFunc(ctx, pyf))
    error workgroup_wait_pyexc(WorkGroup wg)                except +topyexc:
        return wg.wait()

    void pyerr_reraise(runtime.PyError pyerr)   except *:
        runtime.PyErr_ReRaise(pyerr)
