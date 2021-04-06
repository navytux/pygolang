# -*- coding: utf-8 -*-
# Copyright (C) 2021  Nexedi SA and Contributors.
#                     Kirill Smelkov <kirr@nexedi.com>
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
"""Program check_main verifies that __main__ module is correctly installed on
program run."""

from __future__ import print_function, absolute_import

import sys, pickle

class MyUniqueClassXYZ(object):
    def __init__(self, value):
        self.value = value

def main():
    assert MyUniqueClassXYZ.__module__ == '__main__',   MyUniqueClassXYZ.__module__
    assert '__main__' in sys.modules,                   sys.modules
    mainmod  = sys.modules['__main__']
    mainmod_ = __import__('__main__')
    assert mainmod is mainmod_,                         (mainmod, mainmod_)

    # verify that mainmod actually refers to current module
    assert hasattr(mainmod, 'MyUniqueClassXYZ'),        dir(mainmod)

    # pickle/unpickle would also fail if import('__main__') gives module different from current
    obj = MyUniqueClassXYZ(123)
    s = pickle.dumps(obj)
    obj_ = pickle.loads(s)
    assert type(obj_) is MyUniqueClassXYZ,              type(obj)
    assert obj_.value == 123,                           obj_.value

    # ok

assert __name__ == '__main__',  __name__
main()
