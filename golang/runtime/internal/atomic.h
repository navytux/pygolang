#ifndef _NXD_LIBGOLANG_RUNTIME_INTERNAL_ATOMIC_H
#define _NXD_LIBGOLANG_RUNTIME_INTERNAL_ATOMIC_H

// Copyright (C) 2022  Nexedi SA and Contributors.
//                     Kirill Smelkov <kirr@nexedi.com>
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

// Package internal/atomic provides specialized low-level atomic types.

#include <atomic>
#include <stdint.h>

// golang::internal::atomic::
namespace golang {
namespace internal {
namespace atomic {

// int32ForkReset is atomic int32 that is reset to zero in forked child.
//
// It helps to organize locks that do not deadlock in forked child.
// See NOTES in https://man7.org/linux/man-pages/man3/pthread_atfork.3.html for
// rationale and details.
struct int32ForkReset {
private:
    std::atomic<uint64_t> _state; // [fork_epoch]₃₂[value]₃₂

public:
    int32ForkReset();
    int32ForkReset(int32_t value);

    void    store(int32_t value) noexcept;
    int32_t load() noexcept;
    int32_t fetch_add(int32_t delta) noexcept;
};

}}} // golang::internal::atomic::

#endif  // _NXD_LIBGOLANG_RUNTIME_INTERNAL_ATOMIC_H
