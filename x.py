#!/usr/bin/env python

import sys

# make sure `isinstance(x, str)` still returns True even with patched str and x being original python string.
# (else e.g. python import machinery breaks)
strorig = str
class FooMeta(type):
    def __instancecheck__(cls, inst):
        return isinstance(inst, strorig) or super().__instancecheck__(inst)

# XXX -> tweak so that PyUnicode_Check returns true?
#     if this in "|)":
# TypeError: 'in <string>' requires string as left operand, not bytes

_empty = object()

class Foo(bytes, metaclass=FooMeta):

    def __new__(cls, arg=b'', encoding=_empty):
        try:
            arg = memoryview(arg).tobytes()
        except TypeError:
            pass
        else:
            if encoding is not _empty:      # XXX hack
                arg = arg.decode(encoding)

        if type(arg) is strorig:
            #assert encoding is _empty
            arg = arg.encode('UTF-8')

        return super().__new__(cls, arg)

    def __str__(self):
        return self.decode('UTF-8')


    def __hash__(self):
        return super().__hash__()

    def __eq__(a, b):
        b = Foo(b)
        return bytes(a) == bytes(b)

    def __ne__(a, b):
        b = Foo(b)
        return bytes(a) != bytes(b)

    def __getitem__(self, key):
        if not isinstance(key, slice):
            key = slice(key, key+1) # bytes[i] returns int, not subslice
        return super().__getitem__(key)



    def _ustr(self):
        return self.decode('UTF-8')

    # methods that orig str has and bytes misses
    # XXX see UserString
    def isidentifier(self):
        return self._ustr().isidentifier()

    def startswith(self, prefix, start=0, end=sys.maxsize):
        if not isinstance(prefix, tuple):
            prefix = (prefix,)

        bprefix = []
        for p in prefix:
            bprefix.append(Foo(p))
        bprefix = tuple(bprefix)
        return super().startswith(bprefix, start, end)

print()

Astd = 'abc'
Bpatched = Foo(b'def')
print(isinstance(Astd, str))
print(isinstance(Bpatched, str))

#print(__builtins__.str)
__builtins__.str = Foo
#print(str)

print(isinstance(Astd, str))
print(isinstance(Bpatched, str))


print('\n\n-------\n\n\n')
#import itertools    # ok
import code
