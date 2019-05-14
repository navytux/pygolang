#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
"""gpython ... - run python ... with gevent & golang activated

gpython is substitute for standard python interpreter with the following
differences:

- gevent is pre-activated and stdlib is patched to be gevent aware;
- go, chan, select etc are put into builtin namespace;
- default string encoding is always set to UTF-8.
"""

# NOTE gpython is kept out of golang/ , since even just importing e.g. golang.cmd.gpython,
# would import golang, and we need to do gevent monkey-patching ASAP - before that.
#
# we also keep it in gpython/__init__.py instead of gpython.py, since the latter does not
# work correctly with `pip install` (gpython script is installed, but gpython module is not).

# NOTE don't import anything at global scope - we need gevent to be imported first.
from __future__ import print_function, absolute_import


# pymain mimics `python ...`
#
# argv is what comes via `...` without first [0] for python.
def pymain(argv):
    import sys, code, runpy, six
    from os.path import dirname
    from six.moves import input as raw_input

    # interactive console
    if not argv:
        sys.argv = ['']
        sys.path.insert(0, '')  # cwd

        # like code.interact() but with overridden console.raw_input _and_
        # readline imported (code.interact mutually excludes those two).
        try:
            import readline # enable interactive editing
        except ImportError:
            pass

        console = code.InteractiveConsole()
        def _(prompt):
            # python behaviour: don't print '>>>' if stdin is not a tty
            # (builtin raw_input always prints prompt)
            if not sys.stdin.isatty():
                prompt=''
            return raw_input(prompt)
        console.raw_input = _

        console.interact()
        return

    # -c command
    if argv[0] == '-c':
        sys.argv = argv[0:1] + argv[2:] # python leaves '-c' as argv[0]
        sys.path.insert(0, '')          # cwd

        # exec with the same globals `python -c ...` does
        g = {'__name__':    '__main__',
             '__doc__':     None,
             '__package__': None}
        six.exec_(argv[1], g)

    # -m module
    elif argv[0] == '-m':
        # search sys.path for module and run corresponding .py file as script
        sys.argv = argv[1:]
        sys.path.insert(0, '')  # cwd
        runpy.run_module(sys.argv[0], init_globals={'__doc__': None},
                         run_name='__main__', alter_sys=True)

    elif argv[0].startswith('-'):
        print("unknown option: '%s'" % argv[0], file=sys.stderr)
        sys.exit(2)

    # file
    else:
        sys.argv = argv
        filepath = argv[0]
        sys.path.insert(0, dirname(filepath))

        # exec with same globals `python file.py` does
        # XXX use runpy.run_path() instead?
        g = {'__name__':    '__main__',
             '__file__':    filepath,
             '__doc__':     None,
             '__package__': None}
        _execfile(filepath, g)

    return

# execfile was removed in py3
def _execfile(path, globals=None, locals=None):
    import six
    with open(path, "rb") as f:
        src = f.read()
    code = compile(src, path, 'exec')
    six.exec_(code, globals, locals)


def main():
    # set UTF-8 as default encoding.
    # It is ok to import sys before gevent because sys is anyway always
    # imported first, e.g. to support sys.modules.
    import sys
    if sys.getdefaultencoding() != 'utf-8':
        reload(sys)
        sys.setdefaultencoding('utf-8')
        delattr(sys, 'setdefaultencoding')

    # safety check that we are not running from a setuptools entrypoint, where
    # it would be too late to monkey-patch stdlib.
    #
    # (os and signal are imported by python startup itself)
    # (on py3 _thread is imported by the interpreter early to support fine-grained import lock)
    avoid = ['pkg_resources', 'golang', 'socket', 'select', 'threading',
             'thread', 'ssl', 'subprocess']
    # pypy7 made time always pre-imported (https://bitbucket.org/pypy/pypy/commits/6759b768)
    pypy = ('PyPy' in sys.version)
    if not pypy:
        avoid.append('time')
    bad = []
    for mod in avoid:
        if mod in sys.modules:
            bad.append(mod)
    if bad:
        sysmodv = list(sys.modules.keys())
        sysmodv.sort()
        raise RuntimeError('gpython: internal error: the following modules are pre-imported, but must be not:'
                '\n\n\t%s\n\nsys.modules:\n\n\t%s' % (bad, sysmodv))

    # make gevent pre-available & stdlib patched
    from gevent import monkey
    # XXX workaround for gevent vs pypy2 crash.
    # XXX remove when gevent-1.4.1 is relased (https://github.com/gevent/gevent/pull/1357).
    patch_thread=True
    if pypy and sys.version_info.major == 2:
        _ = monkey.patch_thread(existing_locks=False)
        assert _ in (True, None)
        patch_thread=False
    _ = monkey.patch_all(thread=patch_thread)      # XXX sys=True ?
    if _ not in (True, None):   # patched or nothing to do
        # XXX provide details
        raise RuntimeError('gevent monkey-patching failed')

    # put go, chan, select, ... into builtin namespace
    import golang
    from six.moves import builtins
    for k in golang.__all__:
        setattr(builtins, k, getattr(golang, k))

    # sys.executable & friends
    exe = sys.argv[0]

    # on windows there are
    #   gpython-script.py
    #   gpython.exe
    #   gpython.manifest
    # and argv[0] is gpython-script.py
    if exe.endswith('-script.py'):
        exe = exe[:-len('-script.py')]
        exe = exe + '.exe'

    import sys
    sys.executable  = exe
    sys.version    += (' [GPython %s]' % golang.__version__)

    # tail to pymain
    pymain(sys.argv[1:])

if __name__ == '__main__':
    main()
