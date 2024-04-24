#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Program pickle_py2_gpy3_demo demonstrates interoperability in between py2 and py3
# regarding pickled strings.
#
# It initially saves non-ASCII string in pickled form into a file, and on
# further runs tries to load saved object back, appends some tail data to it,
# and saves the result again.
#
# When run on plain py2 everything works as expected: string is initially
# persisted ok, then loaded ok as the same str object, which can be worked with
# as expected, and persisted again ok.
#
# When plain py3 runs this program on the file prepared by py2, loading pickle
# data breaks because, by default, py3 wants to decode *STRING opcodes as ASCII
# and the saved string is not ASCII.
#
# However when run under gpy3, the string is loaded ok as bstr. Since bstr has the
# same semantic as regular str on py2, working with that object produces the
# same result plain py2 would produce when adjusting the data. And then, bstr
# is also persisted ok and via the same *STRING opcodes, that py2 originally
# used for the data.
#
# This way both py2 and gpy3 can interoperate on the same database: py2 can
# produce data, gpy3 can read the data and modify it, and further py2 can load
# updated data, again, just ok.

from __future__ import print_function

from zodbpickle import fastpickle as pickle
import pickletools
from os.path import exists
import sys

def main():
    stor = 'x.pkl'

    print(sys.version)

    if not exists(stor):
        obj = u'αβγ'.encode('utf-8')
    else:
        pkl = readfile(stor)
        print('\nloading pickle:')
        pickletools.dis(pkl)
        obj = pickle.loads(pkl)
        print('\n-> %r\t(%s)' % (obj, obj))

        obj += b' %d' % len(obj)

    print('\nsaving obj: %r\t(%s)' % (obj, obj))
    pkl = pickle.dumps(obj)
    pickletools.dis(pkl)
    writefile(stor, pkl)


def readfile(path):
    with open(path, 'rb') as f:
        return f.read()

def writefile(path, data):
    with open(path, 'wb') as f:
        f.write(data)


if __name__ == '__main__':
    main()
