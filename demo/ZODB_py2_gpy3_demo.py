#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Program ZODB_py2_gpy3_demo demonstrates interoperability in between py2 and py3
# regarding pickled strings in ZODB.
#
# It is similar to pickle_py2_gpy3_demo, but persists data inside ZODB instead
# of raw pickle file.
#
# Please see pickle_py2_gpy3_demo for details.

from __future__ import print_function

from persistent import Persistent
from ZODB.FileStorage import FileStorage
from ZODB.DB import DB
import transaction

from zodbpickle import fastpickle as pickle
import pickletools
import sys


class MyClass(Persistent):
    __slots__ = ('data',)

def main():
    print(sys.version)

    # adjust FileStorage magic so that py3 does not refuse to load FileStorage produced on py2
    fsmod = __import__('ZODB.FileStorage.FileStorage', fromlist=['ZODB'])
    assert hasattr(fsmod, 'packed_version')
    fsmod.packed_version = b'FS21'

    stor = FileStorage('data.fs')
    db   = DB(stor)
    conn = db.open()
    root = conn.root

    if not hasattr(root, 'obj'):
        root.obj = obj = MyClass()
        obj.data = u'αβγ'.encode('utf-8')
    else:
        print('\nloading data:')
        obj = root.obj
        print('\n-> %r\t(%s)' % (obj.data, obj.data))

        obj.data += b' %d' % len(obj.data)

    print('\nsaving data: %r\t(%s)' % (obj.data, obj.data))
    transaction.commit()


if __name__ == '__main__':
    main()
