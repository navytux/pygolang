Pygolang change history
-----------------------

0.0.9 (2021-12-08)
~~~~~~~~~~~~~~~~~~

- Fix deadlock when new context is created from already-canceled parent (`commit 1`__, 2__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/d0688e21
  __ https://lab.nexedi.com/nexedi/pygolang/commit/58d4cbfe

- Add support for `"with"` statement in `sync.WorkGroup`.
  This is sometimes handy and is referred to as *"structured concurrency"*
  in Python world (commit__, discussion__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/6eb80104
  __ https://github.com/gevent/gevent/issues/1697#issuecomment-742708016

- Fix `strconv.unqoute` to handle all input that Go `strconv.Qoute` might produce (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/78b4b41c

- More fixes for `gpython` to be compatible with CPython in how it handles
  program on stdin, interactive session and __main__ module setup (`commit 1`__, 2__, 3__, 4__, 5__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/6cc4bf32
  __ https://lab.nexedi.com/nexedi/pygolang/commit/22fb559a
  __ https://lab.nexedi.com/nexedi/pygolang/commit/95c7cce9
  __ https://lab.nexedi.com/nexedi/pygolang/commit/2351dd27
  __ https://lab.nexedi.com/nexedi/pygolang/commit/e205dbf6


0.0.8 (2020-12-02)
~~~~~~~~~~~~~~~~~~

- Add support for SlapOS (`commit 1`__, 2__, 3__, 4__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/60e89902
  __ https://lab.nexedi.com/nexedi/pygolang/commit/483df486
  __ https://lab.nexedi.com/nexedi/pygolang/commit/92bb5bcc
  __ https://lab.nexedi.com/nexedi/pygolang/commit/0fa9d6e7

- Add way to run tests under `Nexedi testing infrastructure`__ (commit__).

  __ https://www.erp5.com/NXD-Presentation.ci.testing.system.buildout
  __ https://lab.nexedi.com/nexedi/pygolang/commit/d5b1eca0

- Fix `gpython` crash when invoked via relative path as e.g. `./bin/gpython` (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/076cdd8f

- More fixes for `gpython` to be compatible with CPython on command line
  handling (`commit 1`__, 2__, 3__, 4__, 5__, 6__, 7__, 8__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/64088e8a
  __ https://lab.nexedi.com/nexedi/pygolang/commit/167912d3
  __ https://lab.nexedi.com/nexedi/pygolang/commit/26058b5b
  __ https://lab.nexedi.com/nexedi/pygolang/commit/21756bd3
  __ https://lab.nexedi.com/nexedi/pygolang/commit/11b367c6
  __ https://lab.nexedi.com/nexedi/pygolang/commit/8564dfdd
  __ https://lab.nexedi.com/nexedi/pygolang/commit/840a5eae
  __ https://lab.nexedi.com/nexedi/pygolang/commit/cd59f5a5


0.0.7 (2020-09-22)
~~~~~~~~~~~~~~~~~~

- Add way to run `gpython` with either gevent or threads runtime. This allows
  `gpython` usage without forcing projects to switch from threads to greenlets
  (`commit 1`__, 2__, 3__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/0e3da017
  __ https://lab.nexedi.com/nexedi/pygolang/commit/c0282565
  __ https://lab.nexedi.com/nexedi/pygolang/commit/a6b993c8

- Fix `gpython` to be more compatible with CPython on command line handling
  (`commit 1`__, 2__, 3__, 4__, 5__, 6__, 7__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/e6714e49
  __ https://lab.nexedi.com/nexedi/pygolang/commit/70c4c82f
  __ https://lab.nexedi.com/nexedi/pygolang/commit/b47edf42
  __ https://lab.nexedi.com/nexedi/pygolang/commit/a0016938
  __ https://lab.nexedi.com/nexedi/pygolang/commit/51925488
  __ https://lab.nexedi.com/nexedi/pygolang/commit/1f6f31cd
  __ https://lab.nexedi.com/nexedi/pygolang/commit/fb98e594

- Teach `qq` to be usable with both `bytes` and `str` format whatever type
  `qq`'s argument is (`commit 1`__, 2__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/85a1765d
  __ https://lab.nexedi.com/nexedi/pygolang/commit/edc7aaab

- Teach `recover` to always return exception with `.__traceback__` set even on
  Python2 (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/cfcc6db2

- Fix `pyx.build` for develop install (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/34b9c0cf

- Fix `pyx.build` on macOS (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/fb662979

- Add tests for IPython and Pytest integration patches (`commit 1`__,
  2__, 3__, 4__, 5__, 6__, 7__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/0148cb89
  __ https://lab.nexedi.com/nexedi/pygolang/commit/2413b5ba
  __ https://lab.nexedi.com/nexedi/pygolang/commit/42ab98a6
  __ https://lab.nexedi.com/nexedi/pygolang/commit/09629367
  __ https://lab.nexedi.com/nexedi/pygolang/commit/6e31304d
  __ https://lab.nexedi.com/nexedi/pygolang/commit/b938af8b
  __ https://lab.nexedi.com/nexedi/pygolang/commit/a1ac2a45

- Add support for Python38 (`commit 1`__, 2__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/792cbd6c
  __ https://lab.nexedi.com/nexedi/pygolang/commit/1f184095

- Fix ThreadSanitizer/AddressSanitizer support on upcoming Debian 11 (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/49bb8dcd


| |_| |_| |_| |_| |_| |_| |_| |_| *By this release Pygolang was included into* |Nexedi Software Stack|_.

.. |Nexedi Software Stack| replace:: *Nexedi Software Stack*
.. _Nexedi Software Stack: https://stack.nexedi.com


0.0.6 (2020-02-28)
~~~~~~~~~~~~~~~~~~

- Provide support for error chaining. In concurrent systems
  operational stack generally differs from execution code flow, which makes
  code stack traces significantly less useful to understand an error.
  Error chaining gives ability to build operational
  error stack and to inspect resulting errors.
  (`commit 1`__, 2__, 3__, 4__, 5__, 6__, `overview 1`__, `overview 2`__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/fd95c88a
  __ https://lab.nexedi.com/nexedi/pygolang/commit/17798442
  __ https://lab.nexedi.com/nexedi/pygolang/commit/78d0c76f
  __ https://lab.nexedi.com/nexedi/pygolang/commit/337de0d7
  __ https://lab.nexedi.com/nexedi/pygolang/commit/03f88c0b
  __ https://lab.nexedi.com/nexedi/pygolang/commit/80ab5863
  __ https://blog.golang.org/go1.13-errors
  __ https://commandcenter.blogspot.com/2017/12/error-handling-in-upspin.html

- Provide `unicode` ↔ `bytes` conversion:
  `b(obj)` converts str/unicode/bytes obj to UTF-8 encoded bytestring, while
  `u(obj)` converts str/unicode/bytes obj to unicode string. The conversion in
  both encoding and decoding never fails and never looses information:
  `b(u(·))` and `u(b(·))` are always identity for bytes and unicode
  correspondingly, even if bytes input is not valid UTF-8.
  (`commit 1`__, 2__, 3__, 4__, 5__, 6__, 7__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/bcb95cd5
  __ https://lab.nexedi.com/nexedi/pygolang/commit/073d81a8
  __ https://lab.nexedi.com/nexedi/pygolang/commit/5cc679ac
  __ https://lab.nexedi.com/nexedi/pygolang/commit/0561926a
  __ https://lab.nexedi.com/nexedi/pygolang/commit/8c459a99
  __ https://lab.nexedi.com/nexedi/pygolang/commit/3073ac98
  __ https://lab.nexedi.com/nexedi/pygolang/commit/e028cf28

- Provide `sync.RWMutex` (`commit 1`__, 2__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/1ad3c2d5
  __ https://lab.nexedi.com/nexedi/pygolang/commit/a9345a98

- Provide `nil` as alias for `nullptr` and NULL (`commit 1`__, 2__, 3__, 4__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/60f6db6f
  __ https://lab.nexedi.com/nexedi/pygolang/commit/fc1c3e24
  __ https://lab.nexedi.com/nexedi/pygolang/commit/01ade7ac
  __ https://lab.nexedi.com/nexedi/pygolang/commit/230c81c4

- Add `io` package with `io.EOF` and `io.ErrUnexpectedEOF` (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/36ab859c

- Correct `cxx.dict` API to follow libgolang comma-ok style (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/58fcdd87

- Provide `pyx.build.DSO` for projects to build dynamic libraries that
  use/link-to libgolang (`commit 1`__, 2__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/64765688
  __ https://lab.nexedi.com/nexedi/pygolang/commit/cd67996e

- Fix `pyx.build.build_ext` to allow customization (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/8af78fc5

| |_| |_| |_| |_| |_| |_| |_| |_| *This release is driven by* |wendelin.core|_ *v2 needs*.


0.0.5 (2019-11-27)
~~~~~~~~~~~~~~~~~~

- Add support for typed Python channels. For
  example `chan(dtype='C.int')` creates channel whose elements type is C `int`
  instead of Python object. Besides providing runtime type-safety, this allows
  to build interaction in between Python and nogil worlds (`commit 1`__, 2__,
  3__, 4__, 5__, 6__, 7__, 8__, 9__, 10__, 11__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/f2847307
  __ https://lab.nexedi.com/nexedi/pygolang/commit/d6c8862d
  __ https://lab.nexedi.com/nexedi/pygolang/commit/2590e9a7
  __ https://lab.nexedi.com/nexedi/pygolang/commit/47111d3e
  __ https://lab.nexedi.com/nexedi/pygolang/commit/30561db4
  __ https://lab.nexedi.com/nexedi/pygolang/commit/f6fab7b5
  __ https://lab.nexedi.com/nexedi/pygolang/commit/2c8063f4
  __ https://lab.nexedi.com/nexedi/pygolang/commit/3121b290
  __ https://lab.nexedi.com/nexedi/pygolang/commit/77719d8a
  __ https://lab.nexedi.com/nexedi/pygolang/commit/69b80926
  __ https://lab.nexedi.com/nexedi/pygolang/commit/07f9430d

- Provide automatic memory management for C++/Cython/nogil classes.
  Used approach complements `"Automatic multithreaded-safe memory managed
  classes in Cython"` (Gwenaël Samain et al. 2019, `blog post`__) (`commit 1`__,
  2__, 3__, 4__, 5__, 6__, 7__).

  __ https://www.nexedi.com/blog/NXD-Document.Blog.Cypclass
  __ https://lab.nexedi.com/nexedi/pygolang/commit/e82b4fab
  __ https://lab.nexedi.com/nexedi/pygolang/commit/e614d641
  __ https://lab.nexedi.com/nexedi/pygolang/commit/af4a8d80
  __ https://lab.nexedi.com/nexedi/pygolang/commit/b2253abf
  __ https://lab.nexedi.com/nexedi/pygolang/commit/274afa3f
  __ https://lab.nexedi.com/nexedi/pygolang/commit/fd2a6fab
  __ https://lab.nexedi.com/nexedi/pygolang/commit/7f0672aa

- Provide minimal support for interfaces with empty and `error` interfaces
  provided by base library (`commit 1`__, 2__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/5a99b769
  __ https://lab.nexedi.com/nexedi/pygolang/commit/45c8cddd

- Provide `sync.Mutex` and `sync.Sema` as part of both Python and Cython/nogil
  API (`commit 1`__, 2__, 3__, 4__, 5__, 6__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/d99bb6b7
  __ https://lab.nexedi.com/nexedi/pygolang/commit/9c795ca7
  __ https://lab.nexedi.com/nexedi/pygolang/commit/34b7a1f4
  __ https://lab.nexedi.com/nexedi/pygolang/commit/2c1be15e
  __ https://lab.nexedi.com/nexedi/pygolang/commit/e6788170
  __ https://lab.nexedi.com/nexedi/pygolang/commit/548f2df1

- Provide C++/Cython/nogil API for `time` package. Python-level `time` becomes a
  small wrapper around Cython/nogil one (`commit 1`__, 2__, 3__, 4__, 5__, 6__,
  7__, 8__, 9__, 10__, 11__, 12__, 13__, 14__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/32f34607
  __ https://lab.nexedi.com/nexedi/pygolang/commit/0e838833
  __ https://lab.nexedi.com/nexedi/pygolang/commit/106c1b95
  __ https://lab.nexedi.com/nexedi/pygolang/commit/4f6a9e09
  __ https://lab.nexedi.com/nexedi/pygolang/commit/7c929b25
  __ https://lab.nexedi.com/nexedi/pygolang/commit/8c2ac5e9
  __ https://lab.nexedi.com/nexedi/pygolang/commit/a0ba1226
  __ https://lab.nexedi.com/nexedi/pygolang/commit/873cf8aa
  __ https://lab.nexedi.com/nexedi/pygolang/commit/8399ff2d
  __ https://lab.nexedi.com/nexedi/pygolang/commit/419c8950
  __ https://lab.nexedi.com/nexedi/pygolang/commit/1a9dae3b
  __ https://lab.nexedi.com/nexedi/pygolang/commit/b073f6df
  __ https://lab.nexedi.com/nexedi/pygolang/commit/0e6088ec
  __ https://lab.nexedi.com/nexedi/pygolang/commit/73182038

- Provide C++/Cython/nogil API for `context` package. Python-level `context`
  becomes a small wrapper around Cython/nogil one (`commit 1`__, 2__, 3__, 4__,
  5__, 6__, 7__, 8__, 9__, 10__, 11__, 12__, 13__, 14__, 15__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/149ae661
  __ https://lab.nexedi.com/nexedi/pygolang/commit/cc7069e0
  __ https://lab.nexedi.com/nexedi/pygolang/commit/223d7950
  __ https://lab.nexedi.com/nexedi/pygolang/commit/89381488
  __ https://lab.nexedi.com/nexedi/pygolang/commit/9662785b
  __ https://lab.nexedi.com/nexedi/pygolang/commit/34e3c404
  __ https://lab.nexedi.com/nexedi/pygolang/commit/ba2ab242
  __ https://lab.nexedi.com/nexedi/pygolang/commit/9869dc45
  __ https://lab.nexedi.com/nexedi/pygolang/commit/20761c55
  __ https://lab.nexedi.com/nexedi/pygolang/commit/f76c11f3
  __ https://lab.nexedi.com/nexedi/pygolang/commit/281defb2
  __ https://lab.nexedi.com/nexedi/pygolang/commit/66e1e756
  __ https://lab.nexedi.com/nexedi/pygolang/commit/9216e2db
  __ https://lab.nexedi.com/nexedi/pygolang/commit/2a359791
  __ https://lab.nexedi.com/nexedi/pygolang/commit/a6c1c984

- Provide C++/Cython/nogil API for `sync` package. Python-level `sync` becomes a
  small wrapper around Cython/nogil one (`commit 1`__, 2__, 3__, 4__, 5__, 6__, 7__, 8__, 9__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/0fb53e33
  __ https://lab.nexedi.com/nexedi/pygolang/commit/b316e504
  __ https://lab.nexedi.com/nexedi/pygolang/commit/c5c576d2
  __ https://lab.nexedi.com/nexedi/pygolang/commit/5146a416
  __ https://lab.nexedi.com/nexedi/pygolang/commit/4fc6e49c
  __ https://lab.nexedi.com/nexedi/pygolang/commit/a36efe6d
  __ https://lab.nexedi.com/nexedi/pygolang/commit/4fb9b51c
  __ https://lab.nexedi.com/nexedi/pygolang/commit/33cf3113
  __ https://lab.nexedi.com/nexedi/pygolang/commit/6d94fccf

- Add `errors` package with `errors.New` to create new error with provided text (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/a245ab56

- Add `fmt` package with `fmt.sprintf` and `fmt.errorf` to format text into
  strings and errors (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/309963f8

- Add `strings` package with utilities like `strings.has_prefix`,
  `strings.split` and similar (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/0efd4a9a

- Add `cxx` package with `cxx.dict` and `cxx.set` providing ergonomic interface
  over STL hash map and set (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/9785f2d3

- Teach `defer` to chain exceptions (PEP 3134) and adjust traceback dumps to
  include exception cause/context even on Python2 (`commit 1`__, 2__, 3__, 4__, 5__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/6729fe92
  __ https://lab.nexedi.com/nexedi/pygolang/commit/bb9a94c3
  __ https://lab.nexedi.com/nexedi/pygolang/commit/7faaecbc
  __ https://lab.nexedi.com/nexedi/pygolang/commit/06cac90b
  __ https://lab.nexedi.com/nexedi/pygolang/commit/1477dd02

- Provide `defer` as part of C++ API too (`commit 1`__, 2__, 3__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/1d153a45
  __ https://lab.nexedi.com/nexedi/pygolang/commit/14a249cb
  __ https://lab.nexedi.com/nexedi/pygolang/commit/39f40159

- Provide `build_ext` as part of `pyx.build` package API. This allows projects
  to customize the way their Pygolang-based extensions are built (`commit 1`__, 2__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/8f9e5619
  __ https://lab.nexedi.com/nexedi/pygolang/commit/b4feee6f

- Fix `recover` to clean current exception (`commit 1`__, 2__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/9e6ff8bd
  __ https://lab.nexedi.com/nexedi/pygolang/commit/5f76f363

- Fix `select` to not leak object reference on error path (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/e9180de1

- Fix gevent runtime to preserve Python exception state during runtime calls
  (`commit 1`__, 2__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/689dc862
  __ https://lab.nexedi.com/nexedi/pygolang/commit/47fac0a9


| |_| |_| |_| |_| |_| |_| |_| |_| *This release is driven by* |wendelin.core|_ *v2 needs*.
| |_| |_| |_| |_| |_| |_| |_| |_| *This release is dedicated to the memory of* |Бася|_.

.. |wendelin.core| replace:: *wendelin.core*
.. _wendelin.core: https://pypi.org/project/wendelin.core
.. |Бася| replace:: *Бася*
.. _Бася: https://navytux.spb.ru/memory/%D0%91%D0%B0%D1%81%D1%8F/


0.0.4 (2019-09-17)
~~~~~~~~~~~~~~~~~~

- Add ThreadSanitizer, AddressSanitizer and Python debug builds to testing coverage (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/4dc1a7f0

- Fix race bugs in `close`, `recv` and `select` (`commit 1`__, 2__, 3__, 4__, 5__, 6__).
  A 25-years old race condition in Python was also discovered while doing
  quality assurance on concurrency (`commit 7`__, `Python bug`__, `PyPy bug`__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/78e38690
  __ https://lab.nexedi.com/nexedi/pygolang/commit/44737253
  __ https://lab.nexedi.com/nexedi/pygolang/commit/c92a4830
  __ https://lab.nexedi.com/nexedi/pygolang/commit/dcf4ebd1
  __ https://lab.nexedi.com/nexedi/pygolang/commit/65c43848
  __ https://lab.nexedi.com/nexedi/pygolang/commit/5aa1e899
  __ https://lab.nexedi.com/nexedi/pygolang/commit/5142460d
  __ https://bugs.python.org/issue38106
  __ https://foss.heptapod.net/pypy/pypy/-/issues/3072

- If C-level panic causes termination, its argument is now printed (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/f2b77c94


0.0.3 (2019-08-29)
~~~~~~~~~~~~~~~~~~

- Provide Cython/nogil API with goroutines and channels. Cython API is not only
  faster compared to Python version, but also, due to *nogil* property, allows to
  build concurrent systems without limitations imposed by Python's GIL.
  This work was motivated by wendelin.core__ v2, which, due to its design,
  would deadlock if it tries to take the GIL in its pinner thread.
  Implementation of Python-level goroutines and channels becomes tiny wrapper
  around Cython/nogil API. This brings in ~5x speedup to Python-level `golang`
  package along the way (`commit 1`__, 2__, 3__, 4__, 5__, 6__, 7__, 8__, 9__,
  10__, 11__, 12__, 13__, 14__, 15__, 16__, 17__, 18__, 19__, 20__, 21__, 22__,
  23__, 24__, 25__, 26__, 27__).

  __ https://pypi.org/project/wendelin.core
  __ https://lab.nexedi.com/nexedi/pygolang/commit/d98e42e3
  __ https://lab.nexedi.com/nexedi/pygolang/commit/352628b5
  __ https://lab.nexedi.com/nexedi/pygolang/commit/fa667412
  __ https://lab.nexedi.com/nexedi/pygolang/commit/f812faa2
  __ https://lab.nexedi.com/nexedi/pygolang/commit/88eb8fe0
  __ https://lab.nexedi.com/nexedi/pygolang/commit/62bdb806
  __ https://lab.nexedi.com/nexedi/pygolang/commit/8fa3c15b
  __ https://lab.nexedi.com/nexedi/pygolang/commit/ad00be70
  __ https://lab.nexedi.com/nexedi/pygolang/commit/ce8152a2
  __ https://lab.nexedi.com/nexedi/pygolang/commit/7ae8c4f3
  __ https://lab.nexedi.com/nexedi/pygolang/commit/f971a2a8
  __ https://lab.nexedi.com/nexedi/pygolang/commit/83259a1b
  __ https://lab.nexedi.com/nexedi/pygolang/commit/311df9f1
  __ https://lab.nexedi.com/nexedi/pygolang/commit/7e55394d
  __ https://lab.nexedi.com/nexedi/pygolang/commit/790189e3
  __ https://lab.nexedi.com/nexedi/pygolang/commit/a508be9a
  __ https://lab.nexedi.com/nexedi/pygolang/commit/a0714b8e
  __ https://lab.nexedi.com/nexedi/pygolang/commit/1bcb8297
  __ https://lab.nexedi.com/nexedi/pygolang/commit/ef076d3a
  __ https://lab.nexedi.com/nexedi/pygolang/commit/4166dc65
  __ https://lab.nexedi.com/nexedi/pygolang/commit/b9333e00
  __ https://lab.nexedi.com/nexedi/pygolang/commit/d5e74947
  __ https://lab.nexedi.com/nexedi/pygolang/commit/2fc71566
  __ https://lab.nexedi.com/nexedi/pygolang/commit/e4dddf15
  __ https://lab.nexedi.com/nexedi/pygolang/commit/69db91bf
  __ https://lab.nexedi.com/nexedi/pygolang/commit/9efb6575
  __ https://lab.nexedi.com/nexedi/pygolang/commit/3b241983


- Provide way to install Pygolang with extra requirements in the form of
  `pygolang[<package>]`. For example `pygolang[x.perf.benchlib]` additionally
  selects NumPy, `pygolang[pyx.build]` - everything needed by build system, and
  `pygolang[all]` selects everything (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/89a1061a

- Improve tests to exercise the implementation more thoroughly in many
  places (`commit 1`__, 2__, 3__, 4__, 5__, 6__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/773d8fb2
  __ https://lab.nexedi.com/nexedi/pygolang/commit/3e5b5f01
  __ https://lab.nexedi.com/nexedi/pygolang/commit/7f2362dd
  __ https://lab.nexedi.com/nexedi/pygolang/commit/c5810987
  __ https://lab.nexedi.com/nexedi/pygolang/commit/cb5bfdd2
  __ https://lab.nexedi.com/nexedi/pygolang/commit/02f6991f

- Fix race bugs in buffered channel send and receive (`commit 1`__, 2__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/eb8a1fef
  __ https://lab.nexedi.com/nexedi/pygolang/commit/c6bb9eb3

- Fix deadlock in `sync.WorkGroup` tests (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/b8b042c5

- Fix `@func(cls) def name` not to override `name` in calling context (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/924a808c

- Fix `sync.WorkGroup` to propagate all exception types, not only those derived
  from `Exception` (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/79aab7df

- Replace `threading.Event` with `chan` in `sync.WorkGroup` implementation.
  This removes reliance on outside semaphore+waitlist code and speeds up
  `sync.WorkGroup` along the way (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/78d85cdc

- Speedup `sync.WorkGroup` by not using `@func` at runtime (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/94c6160b

- Add benchmarks for `chan`, `select`, `@func` and `defer` (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/3c55ca59

|_| |_| |_| |_| |_| |_| |_| |_| *This release is dedicated to the memory of* |Вера Павловна Супрун|_.

.. |Вера Павловна Супрун| replace:: *Вера Павловна Супрун*
.. _Вера Павловна Супрун: https://navytux.spb.ru/memory/%D0%A2%D1%91%D1%82%D1%8F%20%D0%92%D0%B5%D1%80%D0%B0.pdf#page=3


0.0.2 (2019-05-16)
~~~~~~~~~~~~~~~~~~

- Add `time` package with `time.Timer` and `time.Ticker` (`commit 1`__, 2__, 3__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/81dfefa0
  __ https://lab.nexedi.com/nexedi/pygolang/commit/6e3b3ff4
  __ https://lab.nexedi.com/nexedi/pygolang/commit/9c260fde

- Add support for deadlines and timeouts to `context` package (`commit 1`__, 2__, 3__, 4__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/58ba1765
  __ https://lab.nexedi.com/nexedi/pygolang/commit/e5687f2f
  __ https://lab.nexedi.com/nexedi/pygolang/commit/27f91b78
  __ https://lab.nexedi.com/nexedi/pygolang/commit/b2450310

0.0.1 (2019-05-09)
~~~~~~~~~~~~~~~~~~

- Add support for nil channels (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/2aad64bb

- Add `context` package to propagate cancellation and task-scoped values among
  spawned goroutines (commit__, `overview`__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/e9567c7b
  __ https://blog.golang.org/context

- Add `sync` package with `sync.WorkGroup` to spawn group of goroutines working
  on a common task (`commit 1`__, 2__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/e6bea2cf
  __ https://lab.nexedi.com/nexedi/pygolang/commit/9ee7ba91

- Remove deprecated `@method` (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/262f8986

0.0.0.dev8 (2019-03-24)
~~~~~~~~~~~~~~~~~~~~~~~

- Fix `gpython` to properly initialize `sys.path` (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/6b4990f6

- Fix channel tests to pass irregardless of surround OS load (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/731f39e3

- Deprecate `@method(cls)` in favour of `@func(cls)` (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/942ee900

- Support both `PyPy2` and `PyPy3` (`commit 1`__, 2__, 3__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/da68a8ae
  __ https://lab.nexedi.com/nexedi/pygolang/commit/e847c550
  __ https://lab.nexedi.com/nexedi/pygolang/commit/704d99f0

0.0.0.dev7 (2019-01-16)
~~~~~~~~~~~~~~~~~~~~~~~

- Provide `gpython` interpreter, that sets UTF-8 as default encoding, integrates
  gevent and puts `go`, `chan`, `select` etc into builtin namespace (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/32a21d5b

0.0.0.dev6 (2018-12-13)
~~~~~~~~~~~~~~~~~~~~~~~

- Add `strconv` package with `quote` and `unquote` (`commit 1`__, 2__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/f09701b0
  __ https://lab.nexedi.com/nexedi/pygolang/commit/ed6b7895

- Support `PyPy` as well (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/c859940b

0.0.0.dev5 (2018-10-30)
~~~~~~~~~~~~~~~~~~~~~~~

- Fix `select` bug that was causing several cases to be potentially executed
  at the same time (`commit 1`__, 2__, 3__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/f0b592b4
  __ https://lab.nexedi.com/nexedi/pygolang/commit/b51b8d5d
  __ https://lab.nexedi.com/nexedi/pygolang/commit/2fc6797c

- Add `defer` and `recover` (commit__).
  The implementation is partly inspired by work of Denis Kolodin (1__, 2__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/5146eb0b
  __ https://habr.com/post/191786
  __ https://stackoverflow.com/a/43028386/9456786

- Fix `@method` on Python3 (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/ab69e0fa

- A leaked goroutine no longer prevents whole program to exit (`commit 1`__, 2__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/69cef96e
  __ https://lab.nexedi.com/nexedi/pygolang/commit/ec929991


0.0.0.dev4 (2018-07-04)
~~~~~~~~~~~~~~~~~~~~~~~

- Add `py.bench` program and `golang.testing` package with corresponding bits (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/9bf03d9c

0.0.0.dev3 (2018-07-02)
~~~~~~~~~~~~~~~~~~~~~~~

- Support both Python2 and Python3; `qq` now does not escape printable UTF-8
  characters. (`commit 1`__, 2__, 3__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/02dddb97
  __ https://lab.nexedi.com/nexedi/pygolang/commit/e01e5c2f
  __ https://lab.nexedi.com/nexedi/pygolang/commit/622ccd82

- `golang/x/perf/benchlib:` New module to load & work with data in Go benchmark
  format (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/812e7ed7


0.0.0.dev2 (2018-06-20)
~~~~~~~~~~~~~~~~~~~~~~~

- Turn into full pygolang: `go`, `chan`, `select`, `method` and `gcompat.qq`
  are provided in addition to `gimport` (commit__). The implementation is
  not very fast, but should be working correctly including `select` - `select`
  sends for synchronous channels.

  __ https://lab.nexedi.com/nexedi/pygolang/commit/afa46cf5


0.0.0.dev1 (2018-05-21)
~~~~~~~~~~~~~~~~~~~~~~~

- Initial release; `gimport` functionality only (commit__).

  __ https://lab.nexedi.com/nexedi/pygolang/commit/9c61f254


.. readme_renderer/pypi don't support `.. class:: align-center`
.. |_| unicode:: 0xA0   .. nbsp
