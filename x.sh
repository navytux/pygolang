#!/bin/sh

pypy  -c 'import sys; _ = list(sys.modules.keys()); _.sort(); print(_)' >pypy
pypy3 -c 'import sys; _ = list(sys.modules.keys()); _.sort(); print(_)' >pypy3
