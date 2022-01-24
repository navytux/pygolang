#ifndef _NXD_LIBGOLANG_OS_SIGNAL_H
#define _NXD_LIBGOLANG_OS_SIGNAL_H
//
// Copyright (C) 2021-2022  Nexedi SA and Contributors.
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

// Package signal mirrors Go package signal.
//
//  - `Notify` arranges for signals to be delivered to channels.
//  - `Stop` unsubscribes a channel from signal delivery.
//  - `Ignore` requests signals to be ignored.
//  - `Reset` requests signals to be handled as by default.
//
// See also https://golang.org/pkg/os/signal for Go signal package documentation.

#include <golang/libgolang.h>
#include <golang/os.h>

#include <initializer_list>
#include <vector>


// golang::os::signal::
namespace golang {
namespace os {
namespace signal {

// Notify requests that specified signals, when received, are sent to channel ch.
//
// The sending will be done in non-blocking way. If, at the moment of signal
// reception, the channel is full and not being received-from, the signal won't
// be delivered.
//
// If the list of specified signals is empty, it means "all signals".
LIBGOLANG_API void Notify(chan<os::Signal> ch, const std::initializer_list<os::Signal>& sigv);
LIBGOLANG_API void Notify(chan<os::Signal> ch, const std::vector<os::Signal>& sigv);

// Stop undoes the effect of all previous calls to Notify with specified channel.
//
// After Stop completes, no more signals will be delivered to ch.
LIBGOLANG_API void Stop(chan<os::Signal> ch);

// Ignore requests specified signals to be ignored by the program.
//
// In particular it undoes the effect of all previous calls to Notify with
// specified signals.
//
// After Ignore completes specified signals won't be delivered to any channel.
//
// If the list of specified signals is empty, it means "all signals".
LIBGOLANG_API void Ignore(const std::initializer_list<os::Signal>& sigv);
LIBGOLANG_API void Ignore(const std::vector<os::Signal>& sigv);

// Reset resets specified signals to be handled as by default.
//
// In particular it undoes the effect of all previous calls to Notify with
// specified signals.
//
// After Reset completes specified signals won't be delivered to any channel.
//
// If the list of specified signals is empty, it means "all signals".
LIBGOLANG_API void Reset(const std::initializer_list<os::Signal>& sigv);
LIBGOLANG_API void Reset(const std::vector<os::Signal>& sigv);

}}} // golang::os::signal::

#endif  // _NXD_LIBGOLANG_OS_SIGNAL_H
