========================================
 Pygolang - Go-like features for Python
========================================

Package golang provides Go-like features for Python:

- `go` spawns lightweight thread.
- `chan` and `select` provide channels with Go semantic.
- `method` allows to define methods separate from class.
- `defer` allows to schedule a cleanup from the main control flow.
- `gimport` allows to import python modules by full path in a Go workspace.


Goroutines and channels
-----------------------

`go` spawns a thread, or a coroutine if gevent was activated. It is possible to
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
