===================================================
 Pygolang - Go-like features for Python and Cython
===================================================

Package `golang` provides Go-like features for Python:

- `gpython` is Python interpreter with support for lightweight threads.
- `go` spawns lightweight thread.
- `chan` and `select` provide channels with Go semantic.
- `func` allows to define methods separate from class.
- `defer` allows to schedule a cleanup from the main control flow.
- `error` and package `errors` provide error chaining.
- `b` and `u` provide way to make sure an object is either bytes or unicode.
- `gimport` allows to import python modules by full path in a Go workspace.

Package `golang.pyx` provides__ similar features for Cython/nogil.

__ `Cython/nogil API`_

Additional packages and utilities are also provided__ to close other gaps
between Python/Cython and Go environments.

__ `Additional packages and utilities`_



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
   GPython can be also used with threads - not gevent - runtime. Please see
   `GPython options`_ for details.


Goroutines and channels
-----------------------

`go` spawns a coroutine, or thread if gevent was not activated. It is possible to
exchange data in between either threads or coroutines via channels. `chan`
creates a new channel with Go semantic - either synchronous or buffered. Use
`chan.recv`, `chan.send` and `chan.close` for communication. `nilchan`
stands for nil channel. `select` can be used to multiplex on several
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

By default `chan` creates new channel that can carry arbitrary Python objects.
However type of channel elements can be specified via `chan(dtype=X)` - for
example `chan(dtype='C.int')` creates new channel whose elements are C
integers. `chan.nil(X)` creates typed nil channel. `Cython/nogil API`_
explains how channels with non-Python dtypes, besides in-Python usage, can be
additionally used for interaction in between Python and nogil worlds.


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

If deferred cleanup fails, previously unhandled exception, if any, won't be
lost - it will be chained with (`PEP 3134`__) and included into traceback dump
even on Python2.

__ https://www.python.org/dev/peps/pep-3134/

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


Errors
------

In concurrent systems operational stack generally differs from execution code
flow, which makes code stack traces significantly less useful to understand an
error. Pygolang provides support for error chaining that gives ability to build
operational error stack and to inspect resulting errors:

`error` is error type that can be used by itself or subclassed. By
providing `.Unwrap()` method, an error can optionally wrap another error this
way forming an error chain. `errors.Is` reports whether an item in error chain
matches target. `fmt.Errorf` provides handy way to build wrapping errors.
For example::

   e1 = error("problem")
   e2 = fmt.Errorf("doing something for %s: %w", "joe", e1)
   print(e2)         # prints "doing something for joe: problem"
   errors.Is(e2, e1) # gives True

   # OpError is example class to represents an error of operation op(path).
   class OpError(error):
      def __init__(e, op, path, err):
         e.op   = op
         e.path = path
         e.err  = err

      # .Error() should be used to define what error's string is.
      # it is automatically used by error to also provide both .__str__ and .__repr__.
      def Error(e):
         return "%s %s: %s" % (e.op, e.path, e.err)

      # provided .Unwrap() indicates that this error is chained.
      def Unwrap(e):
         return e.err

   mye = OpError("read", "file.txt", io.ErrUnexpectedEOF)
   print(mye)                          # prints "read file.txt: unexpected EOF"
   errors.Is(mye, io.EOF)              # gives False
   errors.Is(mye. io.ErrUnexpectedEOF) # gives True

Both wrapped and wrapping error can be of arbitrary Python type - not
necessarily of `error` or its subclass.

`error` is also used to represent at Python level an error returned by
Cython/nogil call (see `Cython/nogil API`_) and preserves Cython/nogil error
chain for inspection at Python level.

Pygolang error chaining integrates with Python error chaining and takes
`.__cause__` attribute into account for exception created via `raise X from Y`
(`PEP 3134`__).

__ https://www.python.org/dev/peps/pep-3134/


Strings
-------

`b` and `u` provide way to make sure an object is either bytes or unicode.
`b(obj)` converts str/unicode/bytes obj to UTF-8 encoded bytestring, while
`u(obj)` converts str/unicode/bytes obj to unicode string. For example::

   b("привет мир")   # -> gives bytes corresponding to UTF-8 encoding of "привет мир".

   def f(s):
      s = u(s)       # make sure s is unicode, decoding as UTF-8(*) if it was bytes.
      ...            # (*) but see below about lack of decode errors.

The conversion in both encoding and decoding never fails and never looses
information: `b(u(·))` and `u(b(·))` are always identity for bytes and unicode
correspondingly, even if bytes input is not valid UTF-8.


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


Cython/nogil API
----------------

Cython package `golang` provides *nogil* API with goroutines, channels and
other features that mirror corresponding Python package. Cython API is not only
faster compared to Python version, but also, due to *nogil* property, allows to
build concurrent systems without limitations imposed by Python's GIL. All that
while still programming in Python-like language. Brief description of
Cython/nogil API follows:

`go` spawns new task - a coroutine, or thread, depending on activated runtime.
`chan[T]` represents a channel with Go semantic and elements of type `T`.
Use `makechan[T]` to create new channel, and `chan[T].recv`, `chan[T].send`,
`chan[T].close` for communication. `nil` stands for nil channel. `select`
can be used to multiplex on several channels. For example::

   cdef nogil:
      struct Point:
         int x
         int y

      void worker(chan[int] chi, chan[Point] chp):
         chi.send(1)

         cdef Point p
         p.x = 3
         p.y = 4
         chp.send(p)

      void myfunc():
         cdef chan[int]   chi = makechan[int]()       # synchronous channel of integers
         cdef chan[Point] chp = makechan[Point](3)    # channel with buffer of size 3 and Point elements

         go(worker, chi, chp)

         i = chi.recv()    # will give 1
         p = chp.recv()    # will give Point(3,4)

         chp = nil         # rebind chp to nil channel
         cdef cbool ok
         cdef int j = 33
         _ = select([
             chi.recvs(&i),         # 0
             chi.recvs(&i, &ok),    # 1
             chi.sends(&j),         # 2
             chp.recvs(&p),         # 3
             default,               # 4
         ])
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

Python channels are represented by `pychan` cdef class. Python
channels that carry non-Python elements (`pychan.dtype != DTYPE_PYOBJECT`) can
be converted to Cython/nogil `chan[T]` via `pychan.chan_*()`.
Similarly Cython/nogil `chan[T]` can be wrapped into `pychan` via
`pychan.from_chan_*()`. This provides interaction mechanism
in between *nogil* and Python worlds. For example::

   def myfunc(pychan pych):
      if pych.dtype != DTYPE_INT:
         raise TypeError("expected chan[int]")

      cdef chan[int] ch = pych.chan_int()  # pychan -> chan[int]
      with nogil:
         # use ch in nogil code. Both Python and nogil parts can
         # send/receive on the channel simultaneously.
         ...

   def mytick(): # -> pychan
      cdef chan[int] ch
      with nogil:
         # create a channel that is connected to some nogil task of the program
         ch = ...

      # wrap the channel into pychan. Both Python and nogil parts can
      # send/receive on the channel simultaneously.
      cdef pychan pych = pychan.from_chan_int(ch)  # pychan <- chan[int]
      return pych


`error` is the interface that represents errors. `errors.New` and `fmt.errorf`
provide way to build errors from text. An error can optionally wrap another
error by implementing `errorWrapper` interface and providing `.Unwrap()` method.
`errors.Is` reports whether an item in error chain matches target. `fmt.errorf`
with `%w` specifier provide handy way to build wrapping errors. For example::

   e1 = errors.New("problem")
   e2 = fmt.errorf("doing something for %s: %w", "joe", e1)
   e2.Error()        # gives "doing something for joe: problem"
   errors.Is(e2, e1) # gives True

An `error` can be exposed to Python via `pyerror` cdef class wrapper
instantiated by `pyerror.from_error()`. `pyerror` preserves Cython/nogil error
chain for inspection by Python-level `error.Is`.


`panic` stops normal execution of current goroutine by throwing a C-level
exception. On Python/C boundaries C-level exceptions have to be converted to
Python-level exceptions with `topyexc`. For example::

   cdef void _do_something() nogil:
      ...
      panic("bug")   # hit a bug

   # do_something is called by Python code - it is thus on Python/C boundary
   cdef void do_something() nogil except +topyexc:
      _do_something()

   def pydo_something():
      with nogil:
         do_something()


See |libgolang.h|_ and |golang.pxd|_ for details of the API.
See also |testprog/golang_pyx_user/|_ for demo project that uses Pygolang in
Cython/nogil mode.

.. |libgolang.h| replace:: `libgolang.h`
.. _libgolang.h: https://lab.nexedi.com/nexedi/pygolang/tree/master/golang/libgolang.h

.. |golang.pxd| replace:: `golang.pxd`
.. _golang.pxd: https://lab.nexedi.com/nexedi/pygolang/tree/master/golang/_golang.pxd

.. |testprog/golang_pyx_user/| replace:: `testprog/golang_pyx_user/`
.. _testprog/golang_pyx_user/: https://lab.nexedi.com/nexedi/pygolang/tree/master/golang/pyx/testprog/golang_pyx_user

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

- |golang.context|_ (py__, pyx__) provides contexts to propagate deadlines, cancellation and
  task-scoped values among spawned goroutines [*]_.

  .. |golang.context| replace:: `golang.context`
  .. _golang.context: https://lab.nexedi.com/nexedi/pygolang/tree/master/golang/context.h
  __ https://lab.nexedi.com/nexedi/pygolang/tree/master/golang/context.py
  __ https://lab.nexedi.com/nexedi/pygolang/tree/master/golang/_context.pxd

- |golang.sync|_ (py__, pyx__) provides `sync.WorkGroup` to spawn group of goroutines working
  on a common task. It also provides low-level primitives - for example
  `sync.Once`, `sync.WaitGroup`, `sync.Mutex` and `sync.RWMutex` - that are
  sometimes useful too.

  .. |golang.sync| replace:: `golang.sync`
  .. _golang.sync: https://lab.nexedi.com/nexedi/pygolang/tree/master/golang/sync.h
  __ https://lab.nexedi.com/nexedi/pygolang/tree/master/golang/sync.py
  __ https://lab.nexedi.com/nexedi/pygolang/tree/master/golang/_sync.pxd

- |golang.time|_ (py__, pyx__) provides timers integrated with channels.

  .. |golang.time| replace:: `golang.time`
  .. _golang.time: https://lab.nexedi.com/nexedi/pygolang/tree/master/golang/time.h
  __ https://lab.nexedi.com/nexedi/pygolang/tree/master/golang/time.py
  __ https://lab.nexedi.com/nexedi/pygolang/tree/master/golang/_time.pxd


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

Package |golang.strconv|_ provides direct access to conversion routines, for
example `strconv.quote` and `strconv.unquote`.

.. |golang.strconv| replace:: `golang.strconv`
.. _golang.strconv: https://lab.nexedi.com/nexedi/pygolang/tree/master/golang/strconv.py


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

Package |golang.testing|_ provides corresponding runtime bits, e.g. `testing.B`.

`py.bench` produces output in `Go benchmark format`__, and so benchmark results
can be analyzed and compared with standard Go tools, for example with
`benchstat`__.
Additionally package |golang.x.perf.benchlib|_ can be used to load and process
such benchmarking data in Python.

.. |golang.testing| replace:: `golang.testing`
.. _golang.testing: https://lab.nexedi.com/nexedi/pygolang/tree/master/golang/testing.py
.. |golang.x.perf.benchlib| replace:: `golang.x.perf.benchlib`
.. _golang.x.perf.benchlib: https://lab.nexedi.com/nexedi/pygolang/tree/master/golang/x/perf/benchlib.py
__ https://github.com/golang/proposal/blob/master/design/14313-benchmark-format.md
__ https://godoc.org/golang.org/x/perf/cmd/benchstat


--------

GPython options
---------------

GPython mimics and supports most of Python command-line options, like `gpython
-c <commands>` to run Python statements from command line, or `gpython -m
<module>` to execute a module. Such options have the same meaning as in
standard Python and are not documented here.

GPython-specific options and environment variables are listed below:

`-X gpython.runtime=(gevent|threads)`
    Specify which runtime GPython should use. `gevent` provides lightweight
    coroutines, while with `threads` `go` spawns full OS thread. `gevent` is
    default. The runtime to use can be also specified via `$GPYTHON_RUNTIME`
    environment variable.
