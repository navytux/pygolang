// Copyright (C) 2019-2020  Nexedi SA and Contributors.
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

// Library Libpyxruntime complements Libgolang and provides support for
// Python/Cython runtimes that can be used from nogil code.
//
// See pyx/runtime.h for library overview.

#include "golang/pyx/runtime.h"
#include "golang/sync.h"
#include "golang/errors.h"
using namespace golang;

#include <utility>
using std::tuple;
using std::make_tuple;
using std::tie;

// golang::pyx::runtime::
namespace golang {
namespace pyx {
namespace runtime {


// pyexited indicates whether Python interpreter exited.
static sync::Mutex     *pyexitedMu  = nil; // allocated in _init and never freed not to race
static sync::WaitGroup *pygilTaking = nil; // at exit on dtor vs use.
static bool            pyexited = false;

void _init() {
    pyexitedMu  = new sync::Mutex();
    pygilTaking = new sync::WaitGroup();
}

void _pyatexit_nogil() {
    pyexitedMu->lock();
    pyexited = true;
    pyexitedMu->unlock();

    // make sure all in-flight calls to pygil_ensure are finished
    pygilTaking->wait();
}


// pygil_ensure is like `with gil` but also takes into account possibility
// of python interpreter shutdown.
static tuple<PyGILState_STATE, bool> pygil_ensure() {
    PyGILState_STATE gstate;

    // A C++ thread might still be running while python interpreter is stopped.
    // Verify it is not the case not to crash in PyGILState_Ensure().
    //
    // Tell caller not to run any py code if python interpreter is gone and ignore any error.
    // Python itself behaves the same way on threading cleanup - see e.g.
    // comments in our _golang.pyx::__goviac() about that and also e.g.
    // https://www.riverbankcomputing.com/pipermail/pyqt/2004-July/008196.html
    pyexitedMu->lock();
    if (pyexited) {
        pyexitedMu->unlock();
        return make_tuple(PyGILState_STATE(0), false);
    }

    pygilTaking->add(1);
    pyexitedMu->unlock();
    gstate = PyGILState_Ensure();
    pygilTaking->done();

    return make_tuple(gstate, true);
}

// errors
const global<error> ErrPyStopped = errors::New("Python interpreter is stopped");

error PyErr_Fetch() {
    PyObject *pyexc_type, *pyexc_value, *pyexc_tb;
    PyGILState_STATE gstate;
    bool ok;

    tie(gstate, ok) = pygil_ensure();
    if (!ok) {
        return ErrPyStopped;
    }

        ::PyErr_Fetch(&pyexc_type, &pyexc_value, &pyexc_tb);
        // we now own references to fetched pyexc_*
    PyGILState_Release(gstate);

    // no error
    if (pyexc_type == nil && pyexc_value == nil && pyexc_tb == nil)
        return nil;

    // -> _PyError
    _PyError* _e = new _PyError();
    _e->pyexc_type  = pyexc_type;
    _e->pyexc_value = pyexc_value;
    _e->pyexc_tb    = pyexc_tb;
    return adoptref(static_cast<_error*>(_e));
}

void PyErr_ReRaise(PyError pyerr) {
    PyGILState_STATE gstate;
    bool ok;

    tie(gstate, ok) = pygil_ensure();
    if (!ok) {
        return; // python interpreter is stopped
    }

        // PyErr_Restore takes 1 reference to restored objects.
        // We want to keep pyerr itself alive and valid.
        Py_XINCREF(pyerr->pyexc_type);
        Py_XINCREF(pyerr->pyexc_value);
        Py_XINCREF(pyerr->pyexc_tb);

        ::PyErr_Restore(pyerr->pyexc_type, pyerr->pyexc_value, pyerr->pyexc_tb);
    PyGILState_Release(gstate);
}

_PyError::_PyError()  {}
_PyError::~_PyError() {
    PyGILState_STATE gstate;
    bool ok;

    tie(gstate, ok) = pygil_ensure();
    PyObject *pyexc_type    = this->pyexc_type;
    PyObject *pyexc_value   = this->pyexc_value;
    PyObject *pyexc_tb      = this->pyexc_tb;
    this->pyexc_type  = nil;
    this->pyexc_value = nil;
    this->pyexc_tb    = nil;
    if (!ok) {
        return;
    }

        Py_XDECREF(pyexc_type);
        Py_XDECREF(pyexc_value);
        Py_XDECREF(pyexc_tb);
    PyGILState_Release(gstate);
}

void _PyError::incref() {
    object::incref();
}
void _PyError::decref() {
    if (__decref())
        delete this;
}


string _PyError::Error() {
    return "<PyError>"; // TODO consider putting exception details into error string
}


// PyFunc
PyFunc::PyFunc(PyObject *pyf) {
    PyGILState_STATE gstate = PyGILState_Ensure();
        Py_INCREF(pyf);
        this->pyf = pyf;
    PyGILState_Release(gstate);
}

PyFunc::PyFunc(const PyFunc& from) {
    PyGILState_STATE gstate;
    bool ok;

    tie(gstate, ok) = pygil_ensure();
    if (!ok) {
        pyf = nil; // won't be used
        return;
    }

        pyf = from.pyf;
        Py_INCREF(pyf);
    PyGILState_Release(gstate);
}

PyFunc::~PyFunc() {
    PyGILState_STATE gstate;
    bool ok;

    tie(gstate, ok) = pygil_ensure();
    PyObject *pyf = this->pyf;
    this->pyf = nil;
    if (!ok) {
        return;
    }

        Py_DECREF(pyf);
    PyGILState_Release(gstate);
}

error PyFunc::operator() () const {
    PyGILState_STATE gstate;
    bool ok;

    // e.g. C++ timer thread might still be running while python interpreter is stopped.
    // Verify it is not the case not to crash in PyGILState_Ensure().
    //
    // Don't call the function if python interpreter is gone - i.e. ignore error here.
    // Python itself behaves the same way on threading cleanup - see
    // _golang.pyx::__goviac and pygil_ensure for details.
    tie(gstate, ok) = pygil_ensure();
    if (!ok) {
        return ErrPyStopped;
    }

        error err;
        PyObject *ret = PyObject_CallFunction(pyf, nil);
        if (ret == nil) {
            err = PyErr_Fetch();
        }
        Py_XDECREF(ret);
    PyGILState_Release(gstate);

    return err;
}


}}} // golang::pyx::runtime
