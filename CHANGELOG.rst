Pygolang change history
-----------------------

0.0.2 (2019-05-16)
~~~~~~~~~~~~~~~~~~

- Add `time` package with `time.Timer` and `time.Ticker` (`commit 1`__, 2__, 3__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/81dfefa0
  __ https://lab.nexedi.com/kirr/pygolang/commit/6e3b3ff4
  __ https://lab.nexedi.com/kirr/pygolang/commit/9c260fde

- Add support for deadlines and timeouts to `context` package (`commit 1`__, 2__, 3__, 4__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/58ba1765
  __ https://lab.nexedi.com/kirr/pygolang/commit/e5687f2f
  __ https://lab.nexedi.com/kirr/pygolang/commit/27f91b78
  __ https://lab.nexedi.com/kirr/pygolang/commit/b2450310

0.0.1 (2019-05-09)
~~~~~~~~~~~~~~~~~~

- Add support for nil channels (commit__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/2aad64bb

- Add `context` package to propagate cancellation and task-scoped values among
  spawned goroutines (commit__, `overview`__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/e9567c7b
  __ https://blog.golang.org/context

- Add `sync` package with `sync.WorkGroup` to spawn group of goroutines working
  on a common task (`commit 1`__, 2__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/e6bea2cf
  __ https://lab.nexedi.com/kirr/pygolang/commit/9ee7ba91

- Remove deprecated `@method` (commit__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/262f8986

0.0.0.dev8 (2019-03-24)
~~~~~~~~~~~~~~~~~~~~~~~

- Fix `gpython` to properly initialize `sys.path` (commit__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/6b4990f6

- Fix channel tests to pass irregardless of surround OS load (commit__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/731f39e3

- Deprecate `@method(cls)` in favour of `@func(cls)` (commit__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/942ee900

- Support both `PyPy2` and `PyPy3` (`commit 1`__, 2__, 3__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/da68a8ae
  __ https://lab.nexedi.com/kirr/pygolang/commit/e847c550
  __ https://lab.nexedi.com/kirr/pygolang/commit/704d99f0

0.0.0.dev7 (2019-01-16)
~~~~~~~~~~~~~~~~~~~~~~~

- Provide `gpython` interpreter, that sets UTF-8 as default encoding, integrates
  gevent and puts `go`, `chan`, `select` etc into builtin namespace (commit__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/32a21d5b

0.0.0.dev6 (2018-12-13)
~~~~~~~~~~~~~~~~~~~~~~~

- Add `strconv` package with `quote` and `unquote` (`commit 1`__, 2__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/f09701b0
  __ https://lab.nexedi.com/kirr/pygolang/commit/ed6b7895

- Support `PyPy` as well (commit__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/c859940b

0.0.0.dev5 (2018-10-30)
~~~~~~~~~~~~~~~~~~~~~~~

- Fix `select` bug that was causing several cases to be potentially executed
  at the same time (`commit 1`__, 2__, 3__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/f0b592b4
  __ https://lab.nexedi.com/kirr/pygolang/commit/b51b8d5d
  __ https://lab.nexedi.com/kirr/pygolang/commit/2fc6797c

- Add `defer` and `recover` (commit__).
  The implementation is partly inspired by work of Denis Kolodin (1__, 2__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/5146eb0b
  __ https://habr.com/post/191786
  __ https://stackoverflow.com/a/43028386/9456786

- Fix `@method` on Python3 (commit__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/ab69e0fa

- A leaked goroutine no longer prevents whole program to exit (`commit 1`__, 2__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/69cef96e
  __ https://lab.nexedi.com/kirr/pygolang/commit/ec929991


0.0.0.dev4 (2018-07-04)
~~~~~~~~~~~~~~~~~~~~~~~

- Add `py.bench` program and `golang.testing` package with corresponding bits (commit__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/9bf03d9c

0.0.0.dev3 (2018-07-02)
~~~~~~~~~~~~~~~~~~~~~~~

- Support both Python2 and Python3; `qq` now does not escape printable UTF-8
  characters. (`commit 1`__, 2__, 3__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/02dddb97
  __ https://lab.nexedi.com/kirr/pygolang/commit/e01e5c2f
  __ https://lab.nexedi.com/kirr/pygolang/commit/622ccd82

- `golang/x/perf/benchlib:` New module to load & work with data in Go benchmark
  format (commit__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/812e7ed7


0.0.0.dev2 (2018-06-20)
~~~~~~~~~~~~~~~~~~~~~~~

- Turn into full pygolang: `go`, `chan`, `select`, `method` and `gcompat.qq`
  are provided in addition to `gimport` (commit__). The implementation is
  not very fast, but should be working correctly including `select` - `select`
  sends for synchronous channels.

  __ https://lab.nexedi.com/kirr/pygolang/commit/afa46cf5


0.0.0.dev1 (2018-05-21)
~~~~~~~~~~~~~~~~~~~~~~~

- Initial release; `gimport` functionality only (commit__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/9c61f254
