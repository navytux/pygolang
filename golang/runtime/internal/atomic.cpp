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

#include "golang/runtime/internal/atomic.h"
#include "golang/libgolang.h"

#include <pthread.h>

// golang::internal::atomic::
namespace golang {
namespace internal {
namespace atomic {

// _forkEpoch is incremented in child processes on every fork
//
// NOTE being plain int32_t is ok, but ThreadSanitizer thinks that after fork
// _forkEpoch++ is a race, tries to report it and deadlocks in its own runtime:
// https://github.com/google/sanitizers/issues/1116
//
// -> workaround it via pretentding that _forkEpoch is atomic.
static std::atomic<int32_t> _forkEpoch (0);

static void _forkNewEpoch() {
    _forkEpoch++;
}

void _init() {
    int e = pthread_atfork(/*prepare*/nil, /*inparent*/nil, /*inchild*/_forkNewEpoch);
    if (e != 0)
        panic("pthread_atfork failed");
}


int32ForkReset::int32ForkReset() {
    int32ForkReset& x = *this;
    x.store(0);
}

int32ForkReset::int32ForkReset(int32_t value) {
    int32ForkReset& x = *this;
    x.store(value);
}

void int32ForkReset::store(int32_t value) noexcept {
    int32ForkReset& x = *this;
    x._state.store( (((uint64_t)(_forkEpoch)) << 32) | ((uint64_t)value) );
}

int32_t int32ForkReset::load() noexcept {
    int32ForkReset& x = *this;

    while (1) {
        uint64_t s  = x._state.load();
        int32_t  epoch = (int32_t)(s >> 32);
        int32_t  value = (int32_t)(s & ((1ULL << 32) - 1));
        if (epoch == _forkEpoch)
            return value;

        uint64_t s_ = (((uint64_t)(_forkEpoch)) << 32) | 0;  // reset to 0
        if (x._state.compare_exchange_strong(s, s_))
            return 0;
    }
}

int32_t int32ForkReset::fetch_add(int32_t delta) noexcept {
    int32ForkReset& x = *this;

    while (1) {
        int32_t  value  = x.load(); // resets value to 0 on new fork epoch
        int32_t  value_ = value + delta;
        uint64_t s  = (((uint64_t)(_forkEpoch)) << 32) | ((uint64_t)value);
        uint64_t s_ = (((uint64_t)(_forkEpoch)) << 32) | ((uint64_t)value_);
        if (x._state.compare_exchange_strong(s, s_))
            return value;
    }
}


}}} // golang::internal::atomic::
