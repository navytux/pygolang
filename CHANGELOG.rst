Pygolang change history
=======================

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
