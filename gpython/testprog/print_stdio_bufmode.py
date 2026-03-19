# -*- coding: utf-8 -*-
# Copyright (C) 2025  Nexedi SA and Contributors.
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
"""Program print_stdio_bufmode prints information about stdout/stderr buffering mode."""

from __future__ import print_function, absolute_import

import sys, os


def main():
    null = os.open(os.devnull, os.O_WRONLY)

    def check(subj, ioobj):
        ioobj.write('%s: unbuffered if you see the next line; buffered otherwise\n' % subj)
        ioobj.flush()
        ioobj.write('%s: unbuffered' % subj)  # NOTE: no \n to avoid flush even on line-bufferring
        os.close(ioobj.fileno())
        os.dup2(null, ioobj.fileno())   # not to hit an error when ioobj is closed at the end

    check('stdout', sys.stdout)
    check('stderr', sys.stderr)


if __name__ == '__main__':
    main()
