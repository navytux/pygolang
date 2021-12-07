// Copyright (C) 2019-2021  Nexedi SA and Contributors.
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

// Package context mirrors and amends Go package context.
// See context.h for package overview.

#include "golang/context.h"
#include "golang/cxx.h"
#include "golang/errors.h"
#include "golang/sync.h"
#include "golang/time.h"

#include <math.h>
#include <vector>
using std::pair;
using std::make_pair;
using std::vector;


// golang::context::
namespace golang {
namespace context {

using cxx::set;

static bool _ready(chan<structZ> ch);


// _Background implements root context that is never canceled.
struct _Background final : _Context, object {
    void incref() {
        object::incref();
    }
    void decref() {
        if (__decref())
            delete this;
    }

    double          deadline()              { return INFINITY;  }
    chan<structZ>   done()                  { return nil;       }
    error           err()                   { return nil;       }
    interface       value(const void *key)  { return nil;       }
};

static Context _background = adoptref(static_cast<_Context *>(new _Background()));

Context background() {
    return _background;
}


const global<error> canceled          = errors::New("context canceled");
const global<error> deadlineExceeded  = errors::New("deadline exceeded");


// _BaseCtx is the common base for Contexts implemented in this package.
struct _BaseCtx : _Context, object {
    // parents of this context - either _BaseCtx* or generic Context.
    // does not change after setup.
    vector<Context>  _parentv;

    sync::Mutex             _mu;
    set<refptr<_BaseCtx>>   _children; // children of this context - we propagate cancel there
    error                   _err;
    chan<structZ>           _done;     // chan | nil (nil: => see parent)


    void incref() {
        object::incref();
    }
    void decref() {
        if (__decref())
            delete this;
    }
    virtual ~_BaseCtx() {}

    _BaseCtx(chan<structZ> done, const vector<Context>& parentv) {
        _BaseCtx& ctx = *this;

        ctx._parentv    = parentv;

        // chan: if context can be canceled on its own
        // nil:  if context can not be canceled on its own
        ctx._done       = done;
        if (done == nil) {
            if (parentv.size() != 1)
                panic("BUG: _BaseCtx: done==nil, but len(parentv) != 1");
        }

        // establishes setup so that whenever a parent is canceled,
        // ctx and its children are canceled too.
        refptr<_BaseCtx> bctx = newref(&ctx);

        vector<Context> pforeignv; // parents with !nil .done() for foreign contexts
        for (auto parent : ctx._parentv) {
            // if parent can never be canceled (e.g. it is background) - we
            // don't need to propagate cancel from it.
            chan<structZ> pdone = parent->done();
            if (pdone == nil)
                continue;

            // parent is cancellable - glue to propagate cancel from it to us
            _BaseCtx *_parent = dynamic_cast<_BaseCtx *>(parent._ptr());
            if (_parent != nil) {
                error err = nil;
                _parent->_mu.lock();
                    err = _parent->_err;
                    if (err == nil)
                        _parent->_children.insert(bctx);
                _parent->_mu.unlock();
                if (err != nil)
                    ctx._cancel(err);
            }
            else {
                if (_ready(pdone))
                    ctx._cancel(parent->err());
                else
                    pforeignv.push_back(parent);
            }
        }

        if (pforeignv.size() == 0)
            return;

        // there are some foreign contexts to propagate cancel from
        go([bctx,pforeignv]() {
            vector<_selcase> sel(1+pforeignv.size());
            sel[0] = bctx->_done.recvs();                   // 0
            for (size_t i=0; i<pforeignv.size(); i++)
                sel[1+i] = pforeignv[i]->done().recvs();    // 1 + ...

            int _ = select(sel);

            // 0. nothing - already canceled
            if (_ > 0)
                bctx->_cancel(pforeignv[_-1]->err());
        });
    }

    // _cancel cancels ctx and its children.
    void _cancel(error err) {
        _BaseCtx& ctx = *this;
        return ctx._cancelFrom(nil, err);
    }

    // _cancelFrom cancels ctx and its children.
    // if cancelFrom != nil it indicates which ctx parent cancellation was the cause for ctx cancel.
    virtual void _cancelFrom(Context cancelFrom, error err) {
        _BaseCtx& ctx = *this;

        set<refptr<_BaseCtx>> children;
        ctx._mu.lock();
            if (ctx._err != nil) {
                ctx._mu.unlock();
                return; // already canceled
            }

            ctx._err = err;
            ctx._children.swap(children);
        ctx._mu.unlock();

        if (ctx._done != nil)
            ctx._done.close();

        // no longer need to propagate cancel from parent after we are canceled
        refptr<_BaseCtx> bctx = newref(&ctx);
        for (auto parent : ctx._parentv) {
            if (parent == cancelFrom)
                continue;
            _BaseCtx *_parent = dynamic_cast<_BaseCtx *>(parent._ptr());
            if (_parent != nil) {
                _parent->_mu.lock();
                    _parent->_children.erase(bctx);
                _parent->_mu.unlock();
            }
        }

        // propagate cancel to children
        Context cctx = newref(static_cast<_Context*>(&ctx));
        for (auto child : children)
            child->_cancelFrom(cctx, err);
    }


    chan<structZ> done() {
        _BaseCtx& ctx = *this;

        if (ctx._done != nil)
            return ctx._done;
        return ctx._parentv[0]->done();
    }

    error err() {
        _BaseCtx& ctx = *this;

        ctx._mu.lock();
        defer([&]() {
            ctx._mu.unlock();
        });

        return ctx._err;
    }

    interface value(const void *key) {
        _BaseCtx& ctx = *this;

        for (auto parent : ctx._parentv) {
            interface v = parent->value(key);
            if (v != nil)
                return v;
        }
        return nil;
    }

    double deadline() {
        _BaseCtx& ctx = *this;

        double d = INFINITY;
        for (auto parent : ctx._parentv) {
            double pd = parent->deadline();
            if (pd < d)
                d = pd;
        }
        return d;
    }
};

// _CancelCtx is context that can be canceled.
struct _CancelCtx : _BaseCtx {
    _CancelCtx(const vector<Context>& parentv)
            : _BaseCtx(makechan<structZ>(), parentv) {}
};

// _ValueCtx is context that carries key -> value.
struct _ValueCtx : _BaseCtx {
    // (key, value) specific to this context.
    // the rest of the keys are inherited from parents.
    // does not change after setup.
    const void *_key;
    interface   _value;

    _ValueCtx(const void *key, interface value, Context parent)
            : _BaseCtx(nil, {parent}) {
        _ValueCtx& ctx = *this;

        ctx._key   = key;
        ctx._value = value;
    }

    interface value(const void *key) {
        _ValueCtx& ctx = *this;

        if (ctx._key == key)
            return ctx._value;
        return _BaseCtx::value(key);
    }
};

// _TimeoutCtx is context that is canceled on timeout.
struct _TimeoutCtx : _CancelCtx {
    double       _deadline;
    time::Timer  _timer;

    _TimeoutCtx(double timeout, double deadline, Context parent)
            : _CancelCtx({parent}) {
        _TimeoutCtx& ctx = *this;

        if (timeout <= 0)
            panic("BUG: _TimeoutCtx: timeout <= 0");
        ctx._deadline = deadline;
        refptr<_TimeoutCtx> ctxref = newref(&ctx); // pass ctx reference to timer
        ctx._timer    = time::after_func(timeout, [ctxref]() { ctxref->_cancel(deadlineExceeded); });
    }

    double deadline() {
        _TimeoutCtx& ctx = *this;
        return ctx._deadline;
    }

    // cancel -> stop timer
    void _cancelFrom(Context cancelFrom, error err) {
        _TimeoutCtx& ctx = *this;
        _CancelCtx::_cancelFrom(cancelFrom, err);
        ctx._timer->stop();
    }
};


pair<Context, func<void()>>
with_cancel(Context parent) {
    refptr<_CancelCtx> cctx = adoptref(new _CancelCtx({parent}));
    Context            ctx  = newref  (static_cast<_Context*>(cctx._ptr()));
    return make_pair(ctx, [cctx]() { cctx->_cancel(canceled); });
}

Context
with_value(Context parent, const void *key, interface value) {
    return adoptref(static_cast<_Context*>(new _ValueCtx(key, value, parent)));
}

pair<Context, func<void()>>
with_deadline(Context parent, double deadline) {
    // parent's deadline is before deadline -> just use parent
    double pdead = parent->deadline();
    if (pdead <= deadline)
        return with_cancel(parent);

    // timeout <= 0   -> already canceled
    double timeout = deadline - time::now();
    if (timeout <= 0) {
        Context       ctx;
        func<void()>  cancel;
        tie(ctx, cancel) = with_cancel(parent);
        cancel();
        return make_pair(ctx, cancel);
    }

    refptr<_TimeoutCtx> tctx = adoptref(new _TimeoutCtx(timeout, deadline, parent));
    Context             ctx  = newref  (static_cast<_Context*>(tctx._ptr()));
    return make_pair(ctx, [tctx]() { tctx->_cancel(canceled); });
}

pair<Context, func<void()>>
with_timeout(Context parent, double timeout) {
    return with_deadline(parent, time::now() + timeout);
}

pair<Context, func<void()>>
merge(Context parent1, Context parent2) {
    refptr<_CancelCtx> cctx = adoptref(new _CancelCtx({parent1, parent2}));
    Context            ctx  = newref  (static_cast<_Context*>(cctx._ptr()));
    return make_pair(ctx, [cctx]() { cctx->_cancel(canceled); });
}

// _ready returns whether channel ch is ready.
static bool _ready(chan<structZ> ch) {
    int _ = select({
            ch.recvs(), // 0
            _default,   // 1
    });
    return (_ == 0);
}

// _tctxchildren returns context's children, assuming context is instance of _BaseCtx.
set<Context> _tctxchildren(Context ctx) {
    _BaseCtx *_bctx = dynamic_cast<_BaseCtx*>(ctx._ptr());
    if (_bctx == nil)
        panic("context is not instance of golang.context._BaseCtx");

    set<Context> children;
    _bctx->_mu.lock();
    defer([&]() {
        _bctx->_mu.unlock();
    });

    for (auto bchild : _bctx->_children) {
        Context cchild = newref(static_cast<_Context*>(bchild._ptr()));
        children.insert(cchild);
    }

    return children;
}

}}  // golang::context::
