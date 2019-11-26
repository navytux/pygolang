#ifndef _NXD_LIBGOLANG_PYX_RUNTIME_H
#define _NXD_LIBGOLANG_PYX_RUNTIME_H

// Copyright (C) 2018-2019  Nexedi SA and Contributors.
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
//  - `PyError` represents Python exception, that can be caught/reraised from
//     nogil code, and is interoperated with libgolang `error`.
//  - `PyFunc` represents Python function that can be called from nogil code.

#include <golang/libgolang.h>
#include <Python.h>

#if BUILDING_LIBPYXRUNTIME
#  define LIBPYXRUNTIME_API LIBGOLANG_DSO_EXPORT
#else
#  define LIBPYXRUNTIME_API LIBGOLANG_DSO_IMPORT
#endif


// golang::pyx::runtime::
namespace golang {
namespace pyx {
namespace runtime {

// ErrPyStopped indicates that Python interpreter is stopped.
extern LIBPYXRUNTIME_API const global<error> ErrPyStopped;

// PyError wraps Python exception into error.
// PyError can be used from nogil code.
typedef refptr<class _PyError> PyError;
class _PyError final : public _error, object {
    // retrieved by PyErr_Fetch; each one is holding 1 reference to pointed object
    PyObject *pyexc_type;
    PyObject *pyexc_value;
    PyObject *pyexc_tb;

    // don't new - create only via runtime::PyErr_Fetch();
private:
    _PyError();
    ~_PyError();
    friend error PyErr_Fetch();
    friend void  PyErr_ReRaise(PyError pyerr);
public:
    LIBPYXRUNTIME_API void incref();
    LIBPYXRUNTIME_API void decref();

    // error interface
    string Error();

private:
    _PyError(const _PyError&);  // don't copy
    _PyError(_PyError&&);       // don't move
};

// PyErr_Fetch fetches and clears current Python error.
// It can be called from nogil code.
// It returns either PyError, ErrPyStopped or nil if there is no error.
LIBPYXRUNTIME_API error PyErr_Fetch();

// PyErr_ReRaise reraises Python error with original traceback.
// It can be called from nogil code.
LIBPYXRUNTIME_API void PyErr_ReRaise(PyError pyerr);


// PyFunc represents python function that can be called.
// PyFunc can be used from nogil code.
// PyFunc is safe to use wrt race to python interpreter shutdown.
class PyFunc {
    PyObject *pyf;  // function to call; PyFunc keeps 1 reference to f

public:
    // ctor.
    // PyFunc must be constructed while Python interpreter is alive.
    LIBPYXRUNTIME_API PyFunc(PyObject *pyf);

    // all other methods may be called at any time, including when python
    // interpreter is gone.

    LIBPYXRUNTIME_API PyFunc(const PyFunc& from);   // copy
    LIBPYXRUNTIME_API ~PyFunc();                    // dtor

    // call.
    // returned error is either PyError or ErrPyStopped.
    LIBPYXRUNTIME_API error operator() () const;
};

// libpyxruntime must be initialized before use via _init.
// _pyatexit_nogil must be called when python interpreter is shut down.
//
// These are established by golang/pyx/runtime.pyx initialization, who, in
// turn, is initialized at `import golang` time.
LIBPYXRUNTIME_API void _init();
LIBPYXRUNTIME_API void _pyatexit_nogil();

}}} // golang::pyx::runtime::

#endif  // _NXD_LIBGOLANG_PYX_RUNTIME_H
