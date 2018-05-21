=================================================================
 Pygopath - Import python modules by full path in a Go workspace
=================================================================

Module `gopath` provides way to import python modules by full path in a Go workspace.

For example

::

    lonet = gopath.gimport('lab.nexedi.com/kirr/go123/xnet/lonet')

will import either

- `lab.nexedi.com/kirr/go123/xnet/lonet.py`, or
- `lab.nexedi.com/kirr/go123/xnet/lonet/__init__.py`

located in `src/` under `$GOPATH`.
