#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2018-2019  Nexedi SA and Contributors.
#                          Kirill Smelkov <kirr@nexedi.com>
#
# This program is free software: you can Use, Study, Modify and Redistribute
# it under the terms of the GNU General Public License version 3, or (at your
# option) any later version, as published by the Free Software Foundation.
#
# You can also Link and Combine this program with other software covered by
# the terms of any of the Free Software licenses or any of the Open Source
# Initiative approved licenses and Convey the resulting work. Corresponding
# source of such a combination shall include the source code for all other
# software used.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# See COPYING file for full licensing terms.
# See https://www.nexedi.com/licensing for rationale and options.
"""benchlib - module to load & work with data in Go benchmark format.

https://github.com/golang/proposal/blob/master/design/14313-benchmark-format.md
"""

from __future__ import print_function, absolute_import

import re, io, numpy as np
from collections import OrderedDict

from golang import func


# Benchmark is a collection of benchmark lines.
class Benchmark(list):
    pass

# BenchLine represents one benchmarking line.
#
# it has name, niter and list of measurements with at least one measure.
# it also has labels attached to it.
class BenchLine(object):
    def __init__(self, name, niter, measurev, labels=None):
        self.name  = name
        self.niter = niter
        self.measurev = measurev
        if labels is None:
            labels = OrderedDict()
        self.labels = labels

    def set_labels(self, labels):
        self.labels = labels

# Measure is a value with symbolic unit.
class Measure(object):
    def __init__(self, value, unit):
        self.value = value
        self.unit  = unit

# Unit is a symbolic unit, like "ns/op", "µs/object" or "L1-miss-ns/op"
class Unit(object):
    def __init__(self, unit):
        self.unit = unit

    # eq, hash - so that Unit can be used as key in dict or set
    def __eq__(self, other):
        return (isinstance(other, Unit) and self.unit == other.unit)

    def __hash__(self):
        return hash(self.unit)

    def __ne__(self, other):
        return not self.__eq__(other)


# Stats is a base statistic about Benchmark.
class Stats(object):
    def __init__(self, unit, avg, min, max, std, ninliers, noutliers):
        self.unit = unit
        self.avg = avg
        self.min = min
        self.max = max
        self.std = std
        self.ninliers = ninliers
        self.noutliers = noutliers

    @property
    def nsamples(self):
        return self.ninliers + self.noutliers


# ----------------------------------------

_sp_re = re.compile(r'\s')

# parse_label tries to parse line as label.
#
# returns (key, value).
# if line does not match - (None, None) is returned.
def parse_label(line):
    colon = line.find(':')
    if colon == -1:
        return None, None

    key, value = line[:colon], line[colon+1:]

    # key must not contain space
    if _sp_re.search(key):
        return None, None

    # FIXME key must be unicode lower
    # FIXME key must not contain upper or space
    # XXX also support 'WARNING'

    value = value.strip()  # leading and traling \s XXX for trailing - rstrip only \n ?
    return key, value


# parse_benchline tries to parse line as benchmarking line.
#
# returns BenchLine on success.
# if line does not match - None is returned.
def parse_benchline(line):
    if not line.startswith('Benchmark'):
        return None

    line = line[9:]
    linev = line.split()
    if len(linev) < 4:
        return None

    try:
        return _parse_benchline(linev)
    except Exception:
        # FIXME -> more fine-grained catch, not to skip programming mistakes
        return None

def _parse_benchline(linev):
    name  = linev[0] # FIXME name must start with upper
    niter = int(linev[1])

    # line already matches benchline start. let's try to extract "<value> <unit>" pairs
    tailv = linev[2:]
    measurev = []

    while len(tailv) > 0:
        if tailv[0].startswith('#'):    # tail comment
            break

        if len(tailv) < 2:              # <value> without <unit>
            return None

        value, unit = tailv[:2]
        tailv = tailv[2:]

        value = float(value)
        unit  = Unit(unit)
        unit, scale = unit.normalize()
        measurev.append(Measure(value*scale, unit))

    return BenchLine(name, niter, measurev)


# normalize converts unit into normalized Unit & scale.
#
# It returns base unit and scaling factor to convert values from original
# unit to base one.
#
# For example
#
#	"µs"		-> "s",		1E-6
#	"ms/op"		-> "s/op",     	1E-3
#	"user-s/op"	-> "user-s/op",	1
#
# returns -> Unit, scale.
@func(Unit)
def normalize(self):
    # split unit string into prefix and just unit
    unit = self.unit
    unitv = unit.rsplit('-', 1)     # "L1-miss-ns/op" -> "L1-miss-", "ns/op"
    unit  = unitv[-1]

    # unit -> nom/denom/... ; scale nom to base
    fracv = unit.split('/', 1)
    rescale = 1
    _ = _unitTab.get(fracv[0])
    if _ is not None:
        fracv[0] = _[0]
        rescale  = _[1]

    # rebuild whole unit string
    unitv[-1] = '/'.join(fracv)
    unit = '-'.join(unitv)
    return Unit(unit), rescale


# {} unit -> (base_unit, rescale)
_unitTab = {
        "ns":   ("s", 1E-9),
	u"µs":  ("s", 1E-6),
	"us":   ("s", 1E-6),
	"ms":   ("s", 1E-3),
}



# load loads benchmark data from a reader.
#
# r is required to implement `.readlines()`.
#
# returns -> Benchmark, exit_labels.
# (exit_labels is ordered {} with labels state at end of reading)
def load(r):
    labels = OrderedDict()
    benchv = Benchmark() # of BenchLine

    for line in r.readlines():
        # label
        key, value = parse_label(line)
        if key is not None:
            labels = labels.copy()
            if value:
                if key == 'WARNING':
                    # warnings accumulate, not replace previous ones
                    labels[key] = labels.get(key, ()) + (value,)
                else:
                    labels[key] = value
            else:
                labels.pop(key, None)    # discard
            continue

        # benchmark line
        bl = parse_benchline(line)
        if bl is not None:
            bl.set_labels(labels)
            benchv.append(bl)
            continue

    return benchv, labels

# load_file loads benchmark data from file @ path.
#
# returns -> Benchmark, exit_labels.
def load_file(path):
    with io.open(path, 'r', encoding='utf-8') as f:
        return load(f)


# xload loads benchmark data from a reader with neotest extensions handling.
#
# neotest extensions:
#
# - a line starting with `*** neotest:` denotes start of neotest extension block.
#   The block consists of labels describing e.g. hardware and software on a node.
#   The block ends with a blank line.
#   Labels in the block are not added to benchmarking lines from main stream.
#   The block itself should not contain benchmark lines.
#
# returns -> Benchmark, exit_labels, []extlab.
# (extlab is ordered {} with labels from an extension block)
def xload(r):
    xr = _neotestExtReader(r)
    b, l = load(xr)

    extv = []
    for lineno, text in xr.extblockv:
        bext, lext = load(io.StringIO(text))
        if len(bext) != 0:
            raise RuntimeError("%s:%d: neotest extension block contains benchmark line" \
                    % (getattr(r, name, '?'), lineno))
        extv.append(lext)

    return b, l, extv

# _neotestExtReader is a reader that splits neotest extension data from
# benchmarking data stream.
#
# A reader reading from _neotestExtReader sees original data stream with
# extensions filtered-out. The list of extension blocks found can be accessed
# at .extblockv.
class _neotestExtReader(object):
    def __init__(self, r):
        self.r = r
        self.extblockv = [] # of (lineno, text)
        self._lineno = 0

    def _readline(self):
        l = self.r.readline()
        if l:
            self._lineno += 1
        return l

    def readline(self):
        l = self._readline()
        if not l.startswith('*** neotest:'):
            return l    # EOF='' so also match here

        # new extension block - read up to empty line or EOF
        lineno, ext = self._lineno, [l]
        while 1:
            l = self._readline()
            if l.strip() == "":
                break
            ext.append(l)

        self.extblockv.append((lineno, ''.join(ext)))
        return l

    def readlines(self):
        while 1:
            l = self.readline()
            yield l
            if not l:
                break   # EOF


# xload_file loads benchmark data from file @ path with neotest extensions.
#
# returns -> Benchmark, exit_labels, []extlab.
def xload_file(path):
    with io.open(path, 'r', encoding='utf-8') as f:
        return xload(f)



# bylabel splits Benchmark into several groups of Benchmarks with specified
# labels having same values across a given group.
#
# returns ordered {} labelkey -> Benchmark.
# labelkey = () of (k,v) with k from label_list.
@func(Benchmark)
def bylabel(self, label_list):
    bylabel = OrderedDict() # labelkey -> Benchmark

    for bench in self:
        labelkey = ()
        for k in label_list:
            v = bench.labels.get(k)
            if v is not None:
                labelkey += ((k,v),)

        bb = bylabel.get(labelkey)
        if bb is None:
            bylabel[labelkey] = bb = Benchmark([])
        bb.append(bench)

    return bylabel


# byname splits Benchmark into several Benchmarks each representing BenchLines
# with the same name.
#
# returns ordered {} name -> Benchmark.
@func(Benchmark)
def byname(self):
    byname = OrderedDict() # name -> Benchmark

    for bench in self:
        bb = byname.get(bench.name)
        if bb is None:
            byname[bench.name] = bb = Benchmark([])
        bb.append(bench)

    return byname


# byunit splits Benchmark into several Benchmarks each having BenchLines with
# the same measurements unit.
#
# returns ordered {} unit -> Benchmark.
@func(Benchmark)
def byunit(self):
    byunit = OrderedDict() # unit -> Benchmark

    for bench in self:
        # there can be several measurements with same unit in the same line.
        # (this represents just several measurements of the same thing as part of one line)
        units = OrderedDict()   # just ordered set
        for m in bench.measurev:
            units[m.unit] = 1

        for u in units.keys():
            bb = byunit.get(u)
            if bb is None:
                byunit[u] = bb = Benchmark([])

            mv = [_ for _ in bench.measurev if _.unit == u]
            b = BenchLine(bench.name, bench.niter, mv)
            b.set_labels(bench.labels)
            bb.append(b)

    return byunit

# convert_unit converts benchmark values to be in specified unit.
#
# all original values must have units compatible with the conversion.
#
# returns -> new Benchmark with converted units.
@func(Benchmark)
def convert_unit(self, unit):
    B = Benchmark()
    U = Unit(unit)
    u, uscale = U.normalize()

    for b in self:
        measurev = []
        for m in b.measurev:
            mu, muscale = m.unit.normalize()
            if mu != u:
                raise ValueError('convert unit: units are not convertible: (%s, %s)' % (unit, m.unit))

            measurev.append(Measure(m.value * muscale / uscale, U))

        B.append(BenchLine(b.name, b.niter, measurev, b.labels))

    return B


# stats returns statistics about values in benchmark collection.
#
# all values must have the same units (use .byunit() to prepare).
# returns Stats.
@func(Benchmark)
def stats(self):
    unit = None
    vv = []
    for b in self:
        for m in b.measurev:
            if unit is None:
                unit = m.unit
            if m.unit != unit:
                raise ValueError('stats: different units: (%s, %s)' % (unit, m.unit))
            vv.append(m.value)

    vv, nout = _reject_outliers(vv)
    return Stats(unit, avg=np.mean(vv), min=np.amin(vv), max=np.amax(vv),
            std=np.std(vv), ninliers=len(vv), noutliers=nout)


# ----------------------------------------

@func(BenchLine)
def __repr__(self):
    # XXX +labels
    return 'BenchLine(%r, %d, %r)' % (self.name, self.niter, self.measurev)

@func(Measure)
def __repr__(self):
    return 'Measure(%r, %r)' % (self.value, self.unit)

@func(Unit)
def __repr__(self):
    return 'Unit(%r)' % (self.unit)

@func(Unit)
def __str__(self):
    return self.unit

@func(Stats)
def __str__(self):
    delta = max(self.max - self.avg, self.avg - self.min)
    return '%.2f ±%2.0f%%' % (self.avg, 100. * delta / self.avg)


# benchstat produces output similar to go benchstat program working on one benchmark.
#
# w - writer where to print output.
# B - Benchmark object  # XXX support multiple benchmarks (to print many columns) ?
# split - label names to split on.
def benchstat(w, B, split=[]):
    def emit(text):
        print(text, file=w)

    Bu = B.byunit()
    for i, unit in enumerate(Bu):
        if i != 0:  # not first
            emit('')
        emit("name\t\t\t\t%s" % unit)

        Bl = Bu[unit].bylabel(split)
        for labkey in Bl:
            emit(' '.join(['%s:%s' % (k, v) for k,v in labkey]))

            Bn = Bl[labkey].byname()
            for name in Bn:
                s = Bn[name].stats()
                text = '%-30s\t%20s' % (name, s)
                if s.noutliers != 0:
                    # XXX too many outliers.
                    text += '\t(%d/%d)' % (s.ninliers, s.nsamples)
                emit(text)


#TODO
#def benchdiff(B1, B2):



# ----------------------------------------

# _reject_outliers filters out outliers from data.
#
# returns inliers data, and N(filtered-outliers).
#
# uses the same algorithm as go benchstat:
# https://github.com/golang/perf/blob/ea1fc7ea/benchstat/data.go#L108
def _reject_outliers(data):
    data = np.asarray(data)
    q1, q3 = np.percentile(data, 25), np.percentile(data, 75)
    lo, hi = q1-1.5*(q3-q1), q3+1.5*(q3-q1)
    inliers = data[np.logical_and(lo <= data, data <= hi)]
    return inliers, len(data) - len(inliers)


# another version based on: https://stackoverflow.com/a/16562028 (by Benjamin Bannier).
"""
def _reject_outliers(data, m = 2.):
    data = np.asarray(data)
    d = np.abs(data - np.median(data))
    mdev = np.median(d)
    s = d/mdev if mdev else 0.
    q = s < m
    inliers = data[s<m]
    return inliers, len(data) - len(inliers)
"""



# if invoked as main just print statistics
def main():
    import sys, argparse
    p = argparse.ArgumentParser(description="Print benchmark statistic.")
    p.add_argument("file",    help="input file with benchmark data")
    p.add_argument("--split", default="", help="split benchmarks by labels (default no split)")
    args = p.parse_args()

    B, _ = load_file(args.file)
    benchstat(sys.stdout, B, split=args.split.split(","))

if __name__ == '__main__':
    # XXX hack, so that unicode -> str works out of the box
    import sys; reload(sys)
    sys.setdefaultencoding('UTF-8')
    main()
