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
// See signal.h for package overview.


// Signal package organization
//
// Signals are delivered via regular OS mechanism to _os_sighandler. Because
// signal handler can use only limited subset of system and libc calls(*),
// _os_sighandler further delivers information about received signal to
// _sigrecv_loop running in regular goroutine, which further delivers received
// signals to subscribed clients via regular channel operations. The delivery
// from _os_sighandler to _sigrecv_loop is organized via special
// single-reader/multiple-writers queue implemented with only atomic operations
// and async-signal-safe functions.
//
//
// _sigrecv_loop ← _os_sighandler queue design
//
// The queue accumulates mask of pending received signals and allows the
// receiver to retrieve that mask flushing it to cleared state.
//
// The logic of the queue is explained in terms of its states:
//
// State "Idle":
//   - the reader is not accessing the pending mask and is not blocked.
//   - all writers are not accessing the pending mask.
//   - the mask is clear
//
// State "TxPending":
//   - the reader is not accessing the pending mask and is not blocked.
//   - some writers have updated the pending mask.
//   - the mask is not clear
//
// State "RxBlocked":
//   - the reader accessed the pending mask, found it to be zero, and is in the
//     progress to become blocking, or had already blocked waiting for wakeup
//     from a writer.
//   - all writers are not accessing the pending mask, no writer has woken up
//     the reader.
//
// Reader block/wakeup is done via OS pipe. When the reader decides to block it
// calls sys_read on the reading side of the pipe. When a writer decides to
// wakeup the reader it writes one byte to the sending side of the pipe.
//
// (*) see https://man7.org/linux/man-pages/man7/signal-safety.7.html


// Interoperability with thirdparty code that installs signal handlers
//
// Signal package can be used together with other packages that install signal
// handlers. This interoperability is limited and works only when signal
// package installs signal handlers after thirdparty code. If signal package
// detects that signal handler, that it installed, was somehow changed, it
// raises "collision detected wrt thirdparty sigaction usage" panic.


#include "golang/cxx.h"
#include "golang/os.h"
#include "golang/os/signal.h"
#include "golang/sync.h"
#include "golang/time.h"

#include "golang/runtime/internal/syscall.h"

#include <errno.h>
#include <signal.h>
#include <string.h>
#include <unistd.h>

#include <atomic>
#include <tuple>


#define DEBUG 0
#if DEBUG
#  define debugf(format, ...) fprintf(stderr, format, ##__VA_ARGS__)
#else
#  define debugf(format, ...) do {} while (0)
#endif

// golang::os::signal::
namespace golang {
namespace os {
namespace signal {

namespace sys = golang::internal::syscall;

using std::atomic;
using std::tie;
using std::vector;
using cxx::set;

static void _os_sighandler(int sig, siginfo_t *info, void *ucontext);
static void _notify(int signo);
static void _checksig(int signo);
static void _checkActEqual(const struct sigaction *a, const struct sigaction *b);
static void _spinwaitNextQueueCycle();
static void xsys_sigaction(int signo, const struct sigaction *act, struct sigaction *oldact);
static void xsigemptyset(sigset_t *sa_mask);
static bool _sigact_equal(const struct sigaction *a, const struct sigaction *b);



// queue for _sigrecv_loop <- _os_sighandler
enum _QState { _QIdle, _QTxPending, _QRxBlocked };
static atomic<_QState>  _qstate  (_QIdle);
static atomic<uint64_t> _pending (0);  // signo corresponds to (signo-1)'th bit
#define _MAXSIG 64

static global<os::File> _wakerx = nil; // _sigrecv_loop blocks on _wakerx via read to wait for new signal
static int              _waketx = -1;  // _os_sighandler writes to _waketx to wakeup _sigrecv_loop

static atomic<int>      _txrunning;    // +1'ed during each running _os_sighandler


// subscribed clients are maintained in _registry.
//
// _registry is normally accessed with _regMu locked, or, atomically from
// _os_sighandler to get sigstate and prev_act for a signal.
enum _SigState {
    _SigReset,     // whether we installed previous signal handler (the case after Reset, or final Stop)
    _SigIgnoring,  // whether we installed SIG_IGN (the case after Ignore)
    _SigNotifying, // whether we should be delivering the signal to channels (the case after Notify)
};

struct _SigHandler {
    set<chan<os::Signal>> subscribers; // client channels
    struct sigaction      prev_act;    // sigaction installed before us
    atomic<_SigState>     sigstate;    // which kind of signal handler we installed
};

static sync::Mutex          *_regMu;               // allocated in _init
static atomic<_SigHandler*>  _registry[_MAXSIG+1]; // {} signo -> _SigHandler;  entry remains !nil once set
static bool                  _sigrecv_loop_started = false;

static struct sigaction _actIgnore; // sigaction corresponding to Ignore
static struct sigaction _actNotify; // sigaction corresponding to Notify

void _init() {
    _regMu = new sync::Mutex();

    // create _wakerx <-> _waketx pipe; set _waketx to nonblocking mode
    int vfd[2];
    if (sys::Pipe(vfd) < 0)
        panic("pipe(_wakerx, _waketx)");        // TODO +syserr
    if (sys::Fcntl(vfd[0], F_SETFD, FD_CLOEXEC) < 0)
        panic("fcntl(_wakerx, FD_CLOEXEC)");    // TODO +syserr
    error err;
    tie(_wakerx, err) = os::NewFile(vfd[0], "_wakerx");
    if (err != nil)
        panic("os::newFile(_wakerx");
    _waketx = vfd[1];
    if (sys::Fcntl(_waketx, F_SETFL, O_NONBLOCK) < 0)
        panic("fcntl(_waketx, O_NONBLOCK)");    // TODO +syserr
    if (sys::Fcntl(_waketx, F_SETFD, FD_CLOEXEC) < 0)
        panic("fcntl(_waketx, FD_CLOEXEC)");    // TODO +syserr

    _actIgnore.sa_handler = SIG_IGN;
    _actIgnore.sa_flags   = 0;
    xsigemptyset(&_actIgnore.sa_mask);

    _actNotify.sa_sigaction = _os_sighandler;
    _actNotify.sa_flags     = SA_SIGINFO;
    xsigemptyset(&_actNotify.sa_mask);
}


// _os_sighandler is called by OS on a signal.
static void _os_sighandler(int sig, siginfo_t *info, void *ucontext) {
    _checksig(sig);
    int syserr;

    _txrunning.fetch_add(+1);
    defer([]() {
        _txrunning.fetch_add(-1);
    });

    debugf("\n");
    debugf("SIGHANDLER: invoked with %d\n", sig);

    _SigHandler *h = _registry[sig].load(); // should be !nil if we are here
    _SigState sigstate = h->sigstate.load();

    if (sigstate == _SigNotifying) {
        _pending.fetch_or(1ULL << (sig-1));

        while (1) {
            _QState st = _qstate.load();
            switch (st) {
            case _QIdle:
                debugf("SIGHANDLER: idle\n");
                if (!_qstate.compare_exchange_strong(st, _QTxPending))
                    break;
                goto done;

            case _QTxPending:
                debugf("SIGHANDLER: tx pending\n");
                // another sighandler already transitioned the queue into this state
                goto done;

            case _QRxBlocked:
                debugf("SIGHANDLER: rx blocked\n");
                if (!_qstate.compare_exchange_strong(st, _QTxPending))
                    break;

                debugf("SIGHANDLER: waking up\n");
                // schedule reader wakeup
                syserr = sys::Write(_waketx, "", 1);
                if (syserr == -EAGAIN) // pipe buffer is full => the reader will be woken up anyway
                    syserr = 0;
                if (syserr < 0)
                    panic("write(_waketx) failed"); // TODO +syserr
                goto done;

            default:
                panic("bad _qstate");
            }
        }
    }
done:

    // also call previously-installed handler (e.g. one installed by python's stdlib signal)
    if (sigstate != _SigIgnoring) {
        if (h->prev_act.sa_flags & SA_SIGINFO) {
            h->prev_act.sa_sigaction(sig, info, ucontext);
        }
        else {
            auto sah = h->prev_act.sa_handler;
            if (sah != SIG_IGN) {
                if (sah != SIG_DFL) {
                    sah(sig);
                }
                else {
                    // SIG_DFL && _SigReset - reraise to die if the signal is fatal
                    if (sigstate == _SigReset) {
                        // raise will coredump/term on fatal signal, or ignored
                        // on signals whose default action is to ignore
                        raise(sig);
                    }
                }
            }
        }
    }

    return;
}

// _sigrecv_loop retrieves received signals from _os_sighandler and sends them to subscribed clients.
// it is run in dedicated goroutine and never finishes.
static void _sigrecv_loop() {
    while (1) {
        _QState st = _qstate.load();
        switch (st) {
        case _QIdle:
            debugf("LOOP: idle\n");
            break;

        case _QTxPending:
            debugf("LOOP: tx pending\n");
            if (!_qstate.compare_exchange_strong(st, _QIdle)) // must succeed - no writer is changing
                panic("TxPending -> Idle failed");            // _qstate anymore in _QTxPending state
            break;

        default:
            panic("bad _qstate");
        }

        auto sigp = _pending.exchange(0ULL);

        if (sigp == 0) {
            st = _QIdle;
            if (!_qstate.compare_exchange_strong(st, _QRxBlocked))
                continue;

            debugf("LOOP: -> blocking ...\n");
            char buf[1];
            int n;
            error err;
            tie(n, err) = _wakerx->Read(buf, 1);
            if (err != nil)
                panic("read(_wakerx) failed"); // TODO panic(err) after we can

            debugf("LOOP: woke up\n");
            // by the time we get here _qstate must be reset back from _QRxBlocked
            continue;
        }

        debugf("LOOP: sigp: %lux\n", sigp);

        // deliver fetched signals
        for (int sig = 1; sig <= _MAXSIG; sig++) {
            if ((sigp & (1ULL<<(sig-1))) != 0)
                _notify(sig);
        }
    }
}

static void _notify(int signo) {
    _regMu->lock();
    defer([&]() {
        _regMu->unlock();
    });

    _SigHandler *h = _registry[signo].load();
    if (h == nil)
        return;

    os::Signal sig; sig.signo = signo;
    for (auto ch : h->subscribers) {
        select({
            _default,       // 0
            ch.sends(&sig), // 1
        });
    }
}

static int/*syserr*/ _Notify1(chan<os::Signal> ch, os::Signal sig) {
    _checksig(sig.signo);

    _regMu->lock();
    defer([&]() {
        _regMu->unlock();
    });

    // retrieve current signal action
    struct sigaction cur;
    int syserr = sys::Sigaction(sig.signo, nil, &cur);
    if (syserr < 0) {
        // TODO reenable once we can panic with any object
        //return fmt::errorf("sigaction sig%d: %w", sig.signo, sys::NewErrno(syserr);
        return syserr;
    }

    // retrieve/create sighandler
    atomic<_SigHandler*> *regentry = &_registry[sig.signo];
    _SigHandler *h = regentry->load();
    if (h == nil) {
        h = new _SigHandler();
        h->sigstate.store(_SigReset);
        h->prev_act = cur;
        regentry->store(h);
    }

    // thirdparty code is allowed to install signal handlers after our Reset/Ignore/full-Stop,
    // but not after active Notify.
    _SigState sigstate = h->sigstate.load();
    if (sigstate == _SigNotifying)
        _checkActEqual(&cur, &_actNotify);

    // register our signal handler for sig on first Notify
    if (sigstate != _SigNotifying) {
        // if thirdparty changed signal handler while we were inactive - adjust h.prev_act
        // do the adjustment atomically not to race with _os_sighandler
        struct sigaction *prev_act = (sigstate == _SigIgnoring ? &_actIgnore : &h->prev_act);
        if (!_sigact_equal(&cur, prev_act)) {
            _SigHandler *hold = h;
            h = new _SigHandler();
            h->prev_act = cur;
            h->sigstate.store(_SigReset);
            // h->subscribers remain empty
            prev_act = &h->prev_act;

            regentry->store(h);

            // free old h after we are sure that currently running _os_sighandler is over
            while (_txrunning.load() != 0)
                time::sleep(0); // TODO -> runtime.Gosched
            delete hold;
        }

        // register our sigaction
        struct sigaction old;
        syserr = sys::Sigaction(sig.signo, &_actNotify, &old);
        if (syserr < 0) {
            // TODO reenable once we can panic with any object
            //return fmt::errorf("sigaction sig%d: %w", sig.signo, sys::NewErrno(syserr);
            return syserr;
        }
        _checkActEqual(&old, prev_act);

        // spawn _sigrecv_loop on first Notify request
        if (!_sigrecv_loop_started) {
            go(_sigrecv_loop);
            _sigrecv_loop_started = true;
        }
    }

    h->subscribers.insert(ch);
    h->sigstate.store(_SigNotifying);
    return 0;
}

void Stop(chan<os::Signal> ch) {
    _regMu->lock();
    defer([&]() {
        _regMu->unlock();
    });

    for (int signo = 1; signo <= _MAXSIG; ++signo) {
        atomic<_SigHandler*> *regentry = &_registry[signo];
        _SigHandler *h = regentry->load();

        if (h == nil || (h->sigstate.load() != _SigNotifying))
            continue;

        if (!h->subscribers.has(ch))
            continue;

        if (h->subscribers.size() == 1) { // stopping - ch was the only subscriber
            // reset sigstate early so that _os_sighandler, if it will run (see
            // below about lack of guarantees wrt running old signal handler
            // after sigaction), executes default action by itself.
            h->sigstate.store(_SigReset);

            // sigaction to old handler
            // NOTE sys_sigaction does not guarantee that previously-installed
            // handler is not running after sys_sigaction completes.
            struct sigaction act;
            xsys_sigaction(signo, &h->prev_act, &act);
            _checkActEqual(&act, &_actNotify);

            // wait till signal queue delivers to ch if sig was/is already
            // being handled by _os_sighandler or _sigrecv_loop.
            //
            // (sys_sigaction does not guarantee that previous signal handler
            //  is not being executed after sigaction completes; the old handler
            //  could be also started to run before our call to sys_sigaction)
            _regMu->unlock();
            _spinwaitNextQueueCycle();
            _regMu->lock();
        }

        h->subscribers.erase(ch);
    }
}

static int/*syserr*/ _Ignore1(os::Signal sig) {
    _checksig(sig.signo);

    _regMu->lock();
    defer([&]() {
        _regMu->unlock();
    });

    atomic<_SigHandler*> *regentry = &_registry[sig.signo];
    _SigHandler *h = regentry->load();

    // reset signal handler to SIG_IGN, but remember which handler it was previously there
    // Reset will reset to that instead of hardcoded SIG_DFL
    if (h == nil) {
        h = new _SigHandler();
        h->sigstate.store(_SigIgnoring);
        int syserr = sys::Sigaction(sig.signo, nil, &h->prev_act);
        if (syserr < 0) {
            delete h;
            return syserr; // TODO errctx
        }

        regentry->store(h);
    }

    h->sigstate.store(_SigIgnoring);
    h->subscribers.clear();

    int syserr = sys::Sigaction(sig.signo, &_actIgnore, nil);
    if (syserr < 0)
        return syserr; // TODO errctx

    // no need to wait for delivery to channels to complete

    return 0;
}

static int/*syserr*/ _Reset1(os::Signal sig) {
    _checksig(sig.signo);

    _regMu->lock();
    defer([&]() {
        _regMu->unlock();
    });

    // reset signal handler to what was there previously underlying signal package
    atomic<_SigHandler*> *regentry = &_registry[sig.signo];
    _SigHandler *h = regentry->load();

    if (h == nil)
        return 0;

    _SigState sigstate = h->sigstate.load();
    h->sigstate.store(_SigReset);

    struct sigaction act;
    int syserr = sys::Sigaction(sig.signo, &h->prev_act, &act);
    if (syserr < 0)
        return syserr; // TODO errctx
    if (sigstate == _SigNotifying)
        _checkActEqual(&act, &_actNotify);

    // wait till signal queue delivers to ch if sig was/is already
    // being handled by _os_sighandler or _sigrecv_loop.
    // (see Stop for details)
    _regMu->unlock();
    _spinwaitNextQueueCycle();
    _regMu->lock();

    h->subscribers.clear();
    return 0;
}

// _spinwaitNextQueueCycle waits for all currently-queued signals to complete
// delivery to subscribed channels.
static void _spinwaitNextQueueCycle() {
    // make sure _os_sighandler cycle, if it was running, is complete.
    // if _qstate is _QRxBlocked _os_sighandler transitions it at least once to another state
    while (_txrunning.load() != 0)
        time::sleep(0); // TODO -> runtime.Gosched

    // make sure _sigrecv_loop cycle, if it was running, is complete.
    while (_qstate.load() != _QRxBlocked)
        time::sleep(0); // TODO -> runtime.Gosched
}


// public Notify/Ignore/Reset that accept set of signals.

// _for_all_signals calls f for every signal specified by sigv.
// TODO change f to return error instead of syserr once we can panic with formatted string.
static void _for_all_signals(const vector<os::Signal>& sigv, func<int(os::Signal)> f) {
    if (sigv.size() != 0) {
        for (auto sig : sigv) {
            int syserr = f(sig);
            if (syserr < 0)
                panic("sigaction failed");
        }
    }
    else {
        int nok = 0;
        for (int signo = 1; signo <= _MAXSIG; signo++) {
            int syserr = f(os::_Signal_from_int(signo));
            if (syserr < 0) {
                if (syserr == -EINVAL) {
                    continue; // sigaction refuses to handle SIGKILL/SIGSTOP/32/...
                }
                panic("sigaction failed");
            }
            nok++;
        }

        if (nok == 0)
            panic("sigaction failed for all signals");
    }
}

void Notify(chan<os::Signal> ch, const vector<os::Signal>& sigv) {
    _for_all_signals(sigv, [&](os::Signal sig) {
        return _Notify1(ch, sig);
    });
}

void Ignore(const vector<os::Signal>& sigv) {
    _for_all_signals(sigv, [&](os::Signal sig) {
        return _Ignore1(sig);
    });
}

void Reset(const vector<os::Signal>& sigv) {
    _for_all_signals(sigv, [&](os::Signal sig) {
        return _Reset1(sig);
    });
}


void Notify(chan<os::Signal> ch, const std::initializer_list<os::Signal>& sigv) {
    Notify(ch, vector<os::Signal>(sigv));
}

void Ignore(const std::initializer_list<os::Signal>& sigv) {
    Ignore(vector<os::Signal>(sigv));
}

void Reset(const std::initializer_list<os::Signal>& sigv) {
    Reset(vector<os::Signal>(sigv));
}


static void _checkActEqual(const struct sigaction *a, const struct sigaction *b) {
    if (_sigact_equal(a, b))
        return;

    //fprintf(stderr, "a: %p (%x)\n", a->sa_sigaction, a->sa_flags);
    //fprintf(stderr, "b: %p (%x)\n", b->sa_sigaction, b->sa_flags);
    panic("collision detected wrt thirdparty sigaction usage");
}

static void _checksig(int signo) {
    if (!(1 <= signo && signo <= _MAXSIG))
        panic("invalid signal");
}


static void xsigemptyset(sigset_t *sa_mask) {
    if (sigemptyset(sa_mask) < 0)
        panic("sigemptyset failed"); // must always succeed
}

static void xsys_sigaction(int signo, const struct sigaction *act, struct sigaction *oldact) {
    int syserr = sys::Sigaction(signo, act, oldact);
    if (syserr != 0)
        panic("sigaction failed");   // TODO add errno detail
}

static bool _sigact_equal(const struct sigaction *a, const struct sigaction *b) {
    // don't compare sigaction by memcmp - it will fail because struct sigaction
    // has holes which glibc does not initialize when copying data from
    // retrieved kernel sigaction struct.
    //
    // also don't compare sa_flags fully - glibc tinkers in SA_RESTORER, so
    // retrieving sigaction after installing it might give not exactly the same result.
    bool a_siginfo = (a->sa_flags & SA_SIGINFO);
    bool b_siginfo = (b->sa_flags & SA_SIGINFO);
    if (a_siginfo != b_siginfo) // approximation for a->sa_flags != b->sa_flags
        return false;

    if (a_siginfo & SA_SIGINFO) {
        if (a->sa_sigaction != b->sa_sigaction)
            return false;
    }
    else {
        if (a->sa_handler != b->sa_handler)
            return false;
    }

    // XXX no way to compare sigset_t portably -> let's ignore sa_mask for now
    //return (a->sa_mask == b->sa_mask);
    return true;
}


}}} // golang::os::signal::
