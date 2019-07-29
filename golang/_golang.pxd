# -*- coding: utf-8 -*-
# cython: language_level=2
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

from libcpp cimport nullptr_t, nullptr as nil

cdef extern from "golang.h" namespace "golang" nogil:
    void panic(const char *)
    const char *recover() except +                  # XXX kill `except +` here?

    struct _chan
    cppclass chan[T]:
        chan();
        void send(T *ptx)
        void recv(T *prx)
        bint recv_(T *prx)
        void close()
        unsigned len()
        unsigned cap()
        bint operator==(nullptr_t)
        bint operator!=(nullptr_t)
        void operator=(nullptr_t)
        # XXX == != = vs chan
        _chan *_rawchan()
    chan[T] makechan[T](unsigned size) except +     # XXX kill `except +` here?

    enum _chanop:
        _CHANSEND
        _CHANRECV
        _CHANRECV_
        _DEFAULT
    struct _selcase:
        _chanop op
        void    *data

    # XXX not sure how to wrap just select
    int _chanselect(const _selcase *casev, int casec)

    _selcase _send[T](chan[T] ch, const T *ptx)
    _selcase _recv[T](chan[T] ch, T* prx)
    _selcase _recv_[T](chan[T] ch, T* prx, bint *pok)
    const _selcase _default

"""
cdef nogil:
    struct chan
    struct selcase

#   void chaninit  (chan *ch, unsigned size, unsigned itemsize)
    chan *makechan (unsigned elemsize, unsigned size)
    void chansend  (chan *ch, void *tx)
    bint chanrecv_ (chan *ch, void *rx)
    void chanrecv  (chan *ch, void *rx)
    void chanclose (chan *ch)
    unsigned chanlen(chan *ch)

    void default   (chan *, void *)
    int chanselect (selcase *casev, int casec)
"""
