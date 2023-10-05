// Copyright (C) 2023  Nexedi SA and Contributors.
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

// XXX doctitle

#include <Python.h>
#if PY_MAJOR_VERSION < 3
#include <Python-ast.h> // mod_ty & co
#include <node.h>       // node
#include <graminit.h>   // encoding_decl & co
#include <ast.h>        // PyAST_FromNode & co
#endif

#include <funchook.h>

// py2: wrap PyAST_FromNode so that "utf-8" becomes the default encoding
#if PY_MAJOR_VERSION < 3
static auto   _py_PyAST_FromNode = &PyAST_FromNode;
static mod_ty gpy_PyAST_FromNode(const node* n, PyCompilerFlags* flags,
                                 const char* filename, PyArena* arena)
{
//  fprintf(stderr, "gpy_PyAST_FromNode...\n");
    PyCompilerFlags gflags = {.cf_flags = 0};
    if (flags)
        gflags = *flags;
    if (TYPE(n) != encoding_decl)
        gflags.cf_flags |= PyCF_SOURCE_IS_UTF8;
    return _py_PyAST_FromNode(n, &gflags, filename, arena);
}

static funchook_t* gpy_PyAST_FromNode_hook;
void _set_utf8_as_default_src_encoding() {
    funchook_t *h;
    int err;

//  funchook_set_debug_file("/dev/stderr");

    gpy_PyAST_FromNode_hook = h = funchook_create();
    if (h == NULL) {
        PyErr_NoMemory();
        return;
    }

    err = funchook_prepare(h, (void**)&_py_PyAST_FromNode, (void*)gpy_PyAST_FromNode);
    if (err != 0) {
        PyErr_SetString(PyExc_RuntimeError, funchook_error_message(h));
        return;
    }

    err = funchook_install(h, 0);
    if (err != 0) {
        PyErr_SetString(PyExc_RuntimeError, funchook_error_message(h));
        return;
    }

    // ok
}
#else
void _set_utf8_as_default_src_encoding() {}
#endif
