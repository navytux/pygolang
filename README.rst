========================================
 Pygolang - Go-like features for Python
========================================

Package `golang` provides Go-like features for Python:

- `gpython` is Python interpreter with support for lightweight threads.
- `go` spawns lightweight thread.
- `chan` and `select` provide channels with Go semantic.
- `method` allows to define methods separate from class.
- `defer` allows to schedule a cleanup from the main control flow.
- `gimport` allows to import python modules by full path in a Go workspace.

Additional packages and utilities are also provided__ (2__) to close other gaps
between Python and Go environments.

__ `String conversion`_
__ `Benchmarking and testing`_


GPython
-------

Command `gpython` provides Python interpreter that supports lightweight threads
via tight integration with gevent__. The standard library of GPython is API
compatible with Python standard library, but inplace of OS threads lightweight
coroutines are provided, and IO is internally organized via
libuv__/libev__-based IO scheduler. Consequently programs can spawn lots of
coroutines cheaply, and modules like `time`, `socket`, `ssl`, `subprocess` etc
all could be used from all coroutines simultaneously, in the same blocking way
as if every coroutine was a full OS thread. This gives ability to scale servers
without changing concurrency model and existing code.

__ http://www.gevent.org/
__ http://libuv.org/
__ http://software.schmorp.de/pkg/libev.html


Additionally GPython sets UTF-8 to be default encoding always, and puts `go`,
`chan`, `select` etc into builtin namespace.

.. note::

   GPython is optional and the rest of Pygolang can be used from under standard Python too.
   However without gevent integration `go` spawns full - not lightweight - OS thread.


Goroutines and channels
-----------------------

`go` spawns a coroutine, or thread if gevent was not activated. It is possible to
exchange data in between either threads or coroutines via channels. `chan`
creates a new channel with Go semantic - either synchronous or buffered. Use
`chan.recv`, `chan.send` and `chan.close` for communication. `select` can be
used to multiplex on several channels. For example::

    ch1 = chan()    # synchronous channel
    ch2 = chan(3)   # channel with buffer of size 3

    def _():
        ch1.send('a')
        ch2.send('b')
    go(_)

    ch1.recv()      # will give 'a'
    ch2.recv_()     # will give ('b', True)

    _, _rx = select(
        ch1.recv,           # 0
        ch2.recv_,          # 1
        (ch2.send, obj2),   # 2
        default,            # 3
    )
    if _ == 0:
        # _rx is what was received from ch1
        ...
    if _ == 1:
        # _rx is (rx, ok) of what was received from ch2
        ...
    if _ == 2:
        # we know obj2 was sent to ch2
        ...
    if _ == 3:
        # default case
        ...

Methods
-------

`method` decorator allows to define methods separate from class.

For example::

  @method(MyClass)
  def my_method(self, ...):
      ...

will define `MyClass.my_method()`.


Defer / recover / panic
-----------------------

`defer` allows to schedule a cleanup to be executed when current function
returns. It is similar to `try`/`finally` but does not force the cleanup part
to be far away in the end. For example::

   wc = wcfs.join(zurl)    │     wc = wcfs.join(zurl)
   defer(wc.close)         │     try:
                           │        ...
   ...                     │        ...
   ...                     │        ...
   ...                     │     finally:
                           │        wc.close()

For completeness there is `recover` and `panic` that allow to program with
Go-style error handling, for example::

   def _():
      r = recover()
      if r is not None:
         print("recovered. error was: %s" % (r,))
   defer(_)

   ...

   panic("aaa")

But `recover` and `panic` are probably of less utility since they can be
practically natively modelled with `try`/`except`.

If `defer` is used, the function that uses it must be wrapped with `@func` or
`@method` decorators.

Import
------

`gimport` provides way to import python modules by full path in a Go workspace.

For example

::

    lonet = gimport('lab.nexedi.com/kirr/go123/xnet/lonet')

will import either

- `lab.nexedi.com/kirr/go123/xnet/lonet.py`, or
- `lab.nexedi.com/kirr/go123/xnet/lonet/__init__.py`

located in `src/` under `$GOPATH`.


String conversion
-----------------

`qq` (import from `golang.gcompat`) provides `%q` functionality that quotes as
Go would do. For example the following code will print name quoted in `"`
without escaping printable UTF-8 characters::

   print('hello %s' % qq(name))

`qq` accepts both `str` and `bytes` (`unicode` and `str` on Python2)
and also any other type that can be converted to `str`.

Package `golang.strconv` provides direct access to conversion routines, for
example `strconv.quote` and `strconv.unquote`.


Benchmarking and testing
------------------------

`py.bench` allows to benchmark python code similarly to `go test -bench` and `py.test`.
For example, running `py.bench` on the following code::

    def bench_add(b):
        x, y = 1, 2
        for i in xrange(b.N):
            x + y

gives something like::

    $ py.bench --count=3 x.py
    ...
    pymod: bench_add.py
    Benchmarkadd    50000000        0.020 µs/op
    Benchmarkadd    50000000        0.020 µs/op
    Benchmarkadd    50000000        0.020 µs/op

Package `golang.testing` provides corresponding runtime bits, e.g. `testing.B`.

`py.bench` produces output in `Go benchmark format`__, and so benchmark results
can be analyzed and compared with standard Go tools, for example with
`benchstat`__.
Additionally package `golang.x.perf.benchlib` can be used to load and process
such benchmarking data in Python.

__ https://github.com/golang/proposal/blob/master/design/14313-benchmark-format.md
__ https://godoc.org/golang.org/x/perf/cmd/benchstat
