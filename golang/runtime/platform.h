#ifndef _NXD_LIBGOLANG_RUNTIME_PLATFORM_H
#define _NXD_LIBGOLANG_RUNTIME_PLATFORM_H

// Copyright (C) 2023-2026  Nexedi SA and Contributors.
//                          Kirill Smelkov <kirr@nexedi.com>
//
// This program is free software: you can Use, Study, Modify and Redistribute
// it under the terms of the GNU General Public License version 3, or (at your
// option) any later version, as published by the Free Software Foundation.
//
// You can also Link and Combine this program with other software covered by
// the terms of any of the Free Software licenses or any of the Open Source
// Initiative approved licenses and Convey the resulting work. Corresponding
// source of such a combination shall include the source code for all other
// software used.
//
// This program is distributed WITHOUT ANY WARRANTY; without even the implied
// warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
//
// See COPYING file for full licensing terms.
// See https://www.nexedi.com/licensing for rationale and options.

// Header platform.h provides preprocessor defines that describe target platform.

// LIBGOLANG_ARCH_<X> is defined on architecture X.
//
// List of supported architectures:
//
//      386, amd64
//      arm, arm64
//      mips, mipsle, mips64, mips64le
//      loong64
//      ppc, ppcle, ppc64, ppc64le
//      riscv, riscv64
//      s390, s390x
#if defined(__i386__) || defined(_M_IX86)
# define    LIBGOLANG_ARCH_386      1
#elif defined(__x86_64__) || defined(_M_X64)
# define    LIBGOLANG_ARCH_amd64    1

#elif defined(__arm__) || defined(_M_ARM)
# define    LIBGOLANG_ARCH_arm      1
#elif defined(__aarch64__) || defined(_M_ARM64)
# define    LIBGOLANG_ARCH_arm64    1

#elif defined(__mips__)
# if defined(__mips64)
#  if defined(__MIPSEL__)
#   define  LIBGOLANG_ARCH_mips64le 1
#  else
#   define  LIBGOLANG_ARCH_mips64   1
#  endif
# else
#  if defined(__MIPSEL__)
#   define  LIBGOLANG_ARCH_mipsle   1
#  else
#   define  LIBGOLANG_ARCH_mips     1
#  endif
# endif

#elif defined(__loongarch__)
# if defined(__loongarch_lp64)
#  define   LIBGOLANG_ARCH_loong64  1
# else
#  error "unknown LoongArch variant; please file issue upstream with `cpp -dM` output and other details"
# endif

#elif defined(__powerpc__)
# if defined(__ppc64__)
#  if defined(__LITTLE_ENDIAN__)
#   define  LIBGOLANG_ARCH_ppc64le  1
#  else
#   define  LIBGOLANG_ARCH_ppc64    1
#  endif
# else
#  if defined(__LITTLE_ENDIAN__)
#   define  LIBGOLANG_ARCH_ppcle    1
#  else
#   define  LIBGOLANG_ARCH_ppc      1
#  endif
# endif

#elif defined(__riscv)
# if __riscv_xlen == 64
#  define   LIBGOLANG_ARCH_riscv64  1
# elif __riscv_xlen == 32
#  define   LIBGOLANG_ARCH_riscv    1
# else
#  error "unknown RISC-V variant; please file issue upstream with `cpp -dM` output and other details"
# endif

#elif defined(__s390__)
# if defined(__s390x__)
#  define   LIBGOLANG_ARCH_s390x    1
# else
#  define   LIBGOLANG_ARCH_s390     1
# endif

#else
# error "unsupported architecture; please file issue upstream with `cpp -dM` output and other details"
#endif


// LIBGOLANG_OS_<X> is defined on operating system X.
//
// List of supported operating systems:
//
//      android
//      darwin
//      dragonfly
//      freebsd
//      illumos
//      ios
//      linux
//      netbsd
//      openbsd
//      plan9
//      solaris
//      windows
#ifdef __ANDROID__
# define    LIBGOLANG_OS_android    1

#elif defined(__APPLE__)
# include <TargetConditionals.h>
# if TARGET_OS_IPHONE
#  define   LIBGOLANG_OS_ios        1
# else
#  define   LIBGOLANG_OS_darwin     1
# endif

#elif defined(__DragonFly__)
# define    LIBGOLANG_OS_dragonfly  1

#elif defined(__FreeBSD__)
# define    LIBGOLANG_OS_freebsd    1

#elif defined(__linux__)
# define    LIBGOLANG_OS_linux      1

#elif defined(__NetBSD__)
# define    LIBGOLANG_OS_netbsd     1

#elif defined(__OpenBSD__)
# define    LIBGOLANG_OS_openbsd    1

#elif defined(__PLAN9__)
# define    LIBGOLANG_OS_plan9      1

#elif defined(__illumos__)
# define    LIBGOLANG_OS_illumos    1
#elif defined(__sun) && defined(__SVR4)
# define    LIBGOLANG_OS_solaris    1

#elif defined(_WIN32) || defined(__CYGWIN__)
# define    LIBGOLANG_OS_windows    1

#else
# error "unsupported operating system; please file issue upstream with `cpp -dM` output and other details"
#endif


// LIBGOLANG_CC_<X> is defined on C/C++ compiler X.
//
// List of supported compilers:
//
//      gcc
//      clang
//      msc
#ifdef __clang__
# define    LIBGOLANG_CC_clang      1

#elif defined(_MSC_VER)
# define    LIBGOLANG_CC_msc        1

// NOTE gcc comes last because e.g. clang and icc define __GNUC__ as well
#elif __GNUC__
# define    LIBGOLANG_CC_gcc        1

#else
# error "unsupported compiler; please file issue upstream with `cpp -dM` output and other details"
#endif

#endif  // _NXD_LIBGOLANG_RUNTIME_PLATFORM_H
