# cython: language_level=2

cdef extern from "greenlet/greenlet.h":

    ctypedef class greenlet.greenlet [object PyGreenlet]:
        cdef char *stack_stop
        cdef char *stack_start
        cdef char *stack_copy


    # These are actually macros and so much be included
    # (defined) in each .pxd, as are the two functions
    # that call them.
    greenlet PyGreenlet_GetCurrent()
    void PyGreenlet_Import()


PyGreenlet_Import()

from libc.stdint cimport uintptr_t
from libc.stdio cimport printf

cpdef printg(char *gname):
    cdef greenlet g = PyGreenlet_GetCurrent()
    printf('%p %s.stack: [%p - %p]\n', <void*>g, gname, g.stack_stop, g.stack_start)


def call_using_cstack(f):
    cdef char aaa[128]
    f()
    return aaa[0]
