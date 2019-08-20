===================================================
 Pygolang - Go-like features for Python and Cython
===================================================

Package `golang` provides Go-like features for Python:

- `gpython` is Python interpreter with support for lightweight threads.
- `go` spawns lightweight thread.
- `chan` and `select` provide channels with Go semantic.
- `func` allows to define methods separate from class.
- `defer` allows to schedule a cleanup from the main control flow.
- `gimport` allows to import python modules by full path in a Go workspace.

Package `golang.pyx` provides__ similar features for Cython/nogil.

__ `Cython/nogil API`_

Additional packages and utilities are also provided__ to close other gaps
between Python/Cython and Go environments.

__ `Additional packages and utilities`_

See also appendix for `History of Python concurrency`__.

__ `Appendix I. History of Python concurrency`_


.. contents::
   :depth: 1


GPython
-------

Command `gpython` provides Python interpreter that supports lightweight threads
via tight integration with gevent__. The standard library of GPython is API
compatible with Python standard library, but inplace of OS threads lightweight
coroutines are provided, and IO is internally organized via
libuv__/libev__-based IO scheduler. Consequently programs can spawn lots of
coroutines cheaply, and modules like `time`, `socket`, `ssl`, `subprocess` etc -
all could be used from all coroutines simultaneously, and in the same blocking way
as if every coroutine was a full OS thread. This gives ability to scale programs
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
`chan.recv`, `chan.send` and `chan.close` for communication. `nilchan`
stands for the nil channel. `select` can be used to multiplex on several
channels. For example::

    ch1 = chan()    # synchronous channel
    ch2 = chan(3)   # channel with buffer of size 3

    def _():
        ch1.send('a')
        ch2.send('b')
    go(_)

    ch1.recv()      # will give 'a'
    ch2.recv_()     # will give ('b', True)

    ch2 = nilchan   # rebind ch2 to nil channel
    _, _rx = select(
        ch1.recv,           # 0
        ch1.recv_,          # 1
        (ch1.send, obj),    # 2
        ch2.recv,           # 3
        default,            # 4
    )
    if _ == 0:
        # _rx is what was received from ch1
        ...
    if _ == 1:
        # _rx is (rx, ok) of what was received from ch1
        ...
    if _ == 2:
        # we know obj was sent to ch1
        ...
    if _ == 3:
        # this case will be never selected because
        # send/recv on nil channel block forever.
        ...
    if _ == 4:
        # default case
        ...

Methods
-------

`func` decorator allows to define methods separate from class.

For example::

  @func(MyClass)
  def my_method(self, ...):
      ...

will define `MyClass.my_method()`.

`func` can be also used on just functions, for example::

  @func
  def my_function(...):
      ...


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

If `defer` is used, the function that uses it must be wrapped with `@func`
decorator.


Import
------

XXX import by URL.

`gimport` provides way to import python modules by full path in a Go workspace.

For example

::

    lonet = gimport('lab.nexedi.com/kirr/go123/xnet/lonet')

will import either

- `lab.nexedi.com/kirr/go123/xnet/lonet.py`, or
- `lab.nexedi.com/kirr/go123/xnet/lonet/__init__.py`

located in `src/` under `$GOPATH`.


Cython/nogil API
----------------

Cython package `golang` provides *nogil* API with goroutines, channels and
other features that mirror corresponding Python package.
Cython API is not only faster compared to Python version, but also, due to
*nogil* property, allows to build concurrent systems without limitations
imposed by Python's GIL while still programming in Python-like language.
Brief description if Cython/nogil API follows:

`go` spawns new task - a coroutine, or thread, depending on activated runtime.
`chan[T]` represents a channel with Go semantic and `T` elements.
Use `makechan[T]` to create new channel, and `chan[T].recv`, `chan[T].send`,
`chan[T].close` for communication. `nil` stands for the nil channel. `select`
can be used to multiplex on several channels. For example::

   cdef nogil:
      struct Point:
         int x
         int y

      void worker(chan[int] chi, chan[Point] chp):
         chi.send(1)
         chp.send(Point(3,4))

      void myfunc():
         cdef chan[int]   chi = makechan[int]()       # synchronous channel of integers
         cdef chan[Point] chp = makechan[Point](3)    # channel with buffer of size 3 and Point elements

         go(worker, chi, chp)

         i     = chi.recv()   # will give 1
         p, ok = chp.recv_()  # will give (Point(2,3), True)

         ch2 = nil      # rebind ch2 to nil channel
         _ = select(
             _recv(chi, &i),        # 0
             _recv_(chi, &i, &ok),  # 1
             _send(chi, &j),        # 2
             _recv(chp, &p),        # 3
             _default,              # 4
         )
         if _ == 0:
             # i is what was received from chi
             ...
         if _ == 1:
             # (i, ok) is what was received from chi
             ...
         if _ == 2:
             # we know j was sent to chi
             ...
         if _ == 3:
             # this case will be never selected because
             # send/recv on nil channel block forever.
             ...
         if _ == 4:
             # default case
             ...


XXX `_recv` -> `recv`, `_send` -> `send`, `_default` -> `default`.
XXX `_recv_` -> kill


--------

Additional packages and utilities
---------------------------------

The following additional packages and utilities are also provided to close gaps
between Python/Cython and Go environments:

.. contents::
   :local:

Concurrency
~~~~~~~~~~~

In addition to `go` and channels, the following packages are provided to help
handle concurrency in structured ways:

- `golang.context` provides contexts to propagate deadlines, cancellation and
  task-scoped values among spawned goroutines [*]_.

- `golang.sync` provides `sync.WorkGroup` to spawn group of goroutines working
  on a common task. It also provides low-level primitives - for example
  `sync.Once` and `sync.WaitGroup` - that are sometimes useful too.

- `golang.time` provides timers integrated with channels.

.. [*] See `Go Concurrency Patterns: Context`__ for overview.

__ https://blog.golang.org/context


String conversion
~~~~~~~~~~~~~~~~~

`qq` (import from `golang.gcompat`) provides `%q` functionality that quotes as
Go would do. For example the following code will print name quoted in `"`
without escaping printable UTF-8 characters::

   print('hello %s' % qq(name))

`qq` accepts both `str` and `bytes` (`unicode` and `str` on Python2)
and also any other type that can be converted to `str`.

Package `golang.strconv` provides direct access to conversion routines, for
example `strconv.quote` and `strconv.unquote`.


Benchmarking and testing
~~~~~~~~~~~~~~~~~~~~~~~~

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

--------

Appendix I. History of Python concurrency
-----------------------------------------

This appendix gives brief overview of how Python support for concurrency evolved.
It shows 2 lines of development: based on asynchronous callbacks, and based on tasks.
The tasks approach exposes to programmer high-level synchronous API while
internally low-level asynchronous IO is used by tasks engine. On the other hand
asynchronous approach exposes programmer to deal with asynchronous details.

XXX tasks -> coroutines?
XXX even though ...
XXX incomplete ...

- 1990 Python is created__ (Guido van Rossum).

  __ https://github.com/python/cpython/commit/7f777ed95a

- 1992 Python `adds support for threads`__; the GIL is born (Guido van Rossum).

  __ https://github.com/python/cpython/commit/1984f1e1c6

- 1996 First GIL removal patches (Greg Stein)

  This, and the following GIL-removal attempts, were rejected on the basis that
  performance of single-threaded programs was impacted.

  See `GIL story overview`__ for details.

  __ http://dabeaz.blogspot.com/2011/08/inside-look-at-gil-removal-patch-of.html

- 1996(1999) asyncore/asynchat (https://github.com/python/cpython/commit/0039d7b4e6, Sam Rushing)
- 1996 Medusa__ start (Sam Rushing)

   XXX note on Medusa usage in Zope / first Google crawler.

  __ http://www.nightmare.com/medusa/

- 1998 Stackless Python start (Christian Tismer et al)

XXX coroutines (in std python?)

- 1999/2000 async (Medusa) -> coroutine (shrapnel__) shift (Sam Rushing).
  Shrapnel was published in the open only in 2011.

  __ https://github.com/ironport/shrapnel

- 2001 Twisted starts__ (Glyph Lefkowitz et al)

  __ https://github.com/twisted/twisted/commit/81dd97482d

- XXX Tornado? ZeroMQ?


- Stackless__ implements microthreads for CPython. However it has no builtin
  support for IO and external event loop has to be used so that microthreads
  could do networking IO in a blocking-style which internally is translated
  into OS-level asynchronous IO calls.

  CCP Games (the major company originally backing stackless development) had
  something for this:

  http://www.stackless.com/pipermail/stackless/2015-March/006433.html

  That code was, however, not published and even today Stackless remains a
  patch to CPython, even though its versions for CPython2 and CPython3 seem to
  be maintained.

  __ http://stackless.com/

- However Stackless's microthreads switching functionality "has been
  successfully packaged as a CPython extension called greenlet__" (wikipedia__).

  __ https://github.com/python-greenlet/greenlet
  __ https://en.wikipedia.org/wiki/Stackless_Python

  This way microthreads can be available out of the box for CPython after
  installing greenlet egg.

  ( this still solves only microthreads, not IO problem )

  XXX greenlet start: 2006.

- XXX fibers
- 2012 gruvi (https://github.com/geertj/gruvi)

- A note goes that PyPy has builtin `support for greenlets`__.

  this means that greenlets are not CPython-only and would not be a blocker
  should we eventually try to switch ERP5 to PyPy.

  __ http://doc.pypy.org/en/latest/stackless.html

  XXX pypy stackless start: 2005 (very draft, 021d73d408dad569c5fa0b561c0145f31c8b11f5)

- On top of greenlet there are several libraries that provide blocking-style IO
  integration with microthreads:

  - Concurrent__ (2__) XXX start  2009
  - Eventlet__    XXX start 2008
  - Gevent__      XXX start 2009

  __ http://web.archive.org/web/20130507135412/opensource.hyves.org/concurrence/
  __ https://github.com/concurrence/concurrence
  __ http://eventlet.net/
  __ http://www.gevent.org/

  XXX gevent can adapt Python's stdlib to be coroutine-aware.

- 2012 GvR starts to use yield-from coroutines for asyncio https://github.com/python/asyncio/commit/0b0da72d0d
- 2012(2013) (?) Tulip (Guido van Rossum) -> asyncio, Stackless-based approach
  is explicitly rejected on the basis that there are some "scary implementation
  details". Instead the complexity is thrown onto programmer, with a bit of
  `yield from` syntactic sugar which must be used throughout all function
  invocations that have IO at leaf calls.

  https://lwn.net/Articles/544522/
  https://www.youtube.com/watch?v=sOQLVm0-8Yg   TODO link with Tbegin-Tend about gevent

  There is now 2 high-level API worlds
  - old (synchronous) and new (asynchronous). Much duplication and effort is
  needed for both standard library and other packages in Python ecosystem.

- 2015 async/await (https://www.python.org/dev/peps/pep-0492/)

- XXX goless, offset, pychan
