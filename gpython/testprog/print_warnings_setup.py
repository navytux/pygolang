# -*- coding: utf-8 -*-
# Copyright (C) 2020  Nexedi SA and Contributors.
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
"""Program print_warnings_setup prints information about warnings module
configuration."""

from __future__ import print_function, absolute_import

import sys, warnings, re

def main():
    print('sys.warnoptions: %s' % sys.warnoptions)
    print('\nwarnings.filters:')
    for f in warnings.filters:
        print_filter(f)

def print_filter(f):
    # see Lib/warnings.py
    action, message, klass, module, line = f
    message = wstr(message)
    module  = wstr(module)
    klass   = klass.__name__
    if line == 0:
        line = '*'
    print('- %s:%s:%s:%s:%s' % (action, message, klass, module, line))

# wstr returns str corresponding to warning filter's message or module.
REPattern = re.compile('').__class__
def wstr(obj):
    if obj is None:
        return ''
    if isinstance(obj, REPattern):
        return obj.pattern
    return obj


if __name__ == '__main__':
    main()
