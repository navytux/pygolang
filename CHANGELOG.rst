Pygolang change history
=======================

0.0.0.dev4 (2018-07-04)
-----------------------

- Add `py.bench` program and `golang.testing` package with corresponding bits (commit__).

  `py.bench` allows to benchmark python code similarly to `go test -bench` and `py.test`.
  For example, running py.bench on the following code::

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

  __ https://lab.nexedi.com/kirr/pygolang/commit/9bf03d9c

0.0.0.dev3 (2018-07-02)
-----------------------

- Support both Python2 and Python3; `qq` now does not escape printable UTF-8
  characters. (`commit 1`__, 2__, 3__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/02dddb97
  __ https://lab.nexedi.com/kirr/pygolang/commit/e01e5c2f
  __ https://lab.nexedi.com/kirr/pygolang/commit/622ccd82

- `golang/x/perf/benchlib:` New module to load & work with data in Go benchmark
  format (commit__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/812e7ed7


0.0.0.dev2 (2018-06-20)
-----------------------

- Turn into full pygolang: `go`, `chan`, `select`, `method` and `gcompat.qq`
  are provided in addition to `gimport` (commit__). The implementation is
  not very fast, but should be working correctly including `select` - `select`
  sends for synchronous channels.

  __ https://lab.nexedi.com/kirr/pygolang/commit/afa46cf5


0.0.0.dev1 (2018-05-21)
-----------------------

- Initial release; `gimport` functionality only (commit__).

  __ https://lab.nexedi.com/kirr/pygolang/commit/9c61f254
