// Copyright (C) 2019  Nexedi SA and Contributors.
//                     Kirill Smelkov <kirr@nexedi.com>
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
static sync::Mutex     *pyexitedMu  = NULL; // allocated in _init and never freed not to race
static sync::WaitGroup *pygilTaking = NULL; // at exit on dtor vs use.
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
        pyf = NULL; // won't be used
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
    this->pyf = NULL;
    if (!ok) {
        return;
    }

        Py_DECREF(pyf);
    PyGILState_Release(gstate);
}

void PyFunc::operator() () const {
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
        return;
    }

        ok = true;
        PyObject *ret = PyObject_CallFunction(pyf, NULL);
        if (ret == NULL && !pyexited) {
            PyErr_PrintEx(0);
            ok = false;
        }
        Py_XDECREF(ret);
    PyGILState_Release(gstate);

    // XXX exception -> exit program with traceback (same as in go) ?
    //if (!ok)
    //    panic("pycall failed");
}


}}} // golang::pyx::runtime
