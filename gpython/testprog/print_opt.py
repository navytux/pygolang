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
"""Program print_opt prints information about optimizations."""

from __future__ import print_function, absolute_import

import sys, os, os.path, tempfile, shutil

def main():
    print('sys.flags.debug:      %s' % sys.flags.debug)
    print('sys.flags.optimize:   %s' % sys.flags.optimize)
    print('__debug__:            %s' % __debug__)
    print('assert:               %s' % is_assert_enabled())
    print('docstrings:           %s' % is_docstrings_enabled())
    print('import mod.py:        %s' % modpy_imports_from())


# is_assert_enabled returns whether assert statements are enabled.
def is_assert_enabled():
    try:
        assert False # must raise AssertionError
    except AssertionError:
        return True
    else:
        return False

# is_docstrings_enabled returns whether docstrings are enabled.
def is_docstrings_enabled():
    def _():
        """hello world"""
    if _.__doc__ is None:
        return False
    if _.__doc__ == "hello world":
        return True
    raise AssertionError(_.__doc__)

# modpy returns name for compiled version of python module mod.py
def modpy_imports_from():
    try:
        import mod
    except ImportError:
        # ok - should not be there
        pass
    else:
        raise AssertionError("module 'mod' is already there")

    tmpd = tempfile.mkdtemp('', 'modpy_imports_from')
    try:
        pymod = "%s/mod.py" % tmpd
        with open(pymod, "w") as f:
            f.write("# hello up there\n")

        sys.path.insert(0, tmpd)
        import mod

        files = set()
        for dirpath, dirnames, filenames in os.walk(tmpd):
            for _ in filenames:
                f = '%s/%s' % (dirpath, _)
                if f.startswith(tmpd+'/'):
                    f = f[len(tmpd+'/'):]
                files.add(f)


        files.remove("mod.py") # must be there | raises if not
        if len(files) == 0:
            from_ = "mod.py"   # source-only import
        else:
            if len(files) != 1:
                raise AssertionError("mod.py -> multiple compiled files (%s)" % (files,))

            from_ = files.pop()

        return from_

    finally:
        shutil.rmtree(tmpd)


if __name__ == '__main__':
    main()
