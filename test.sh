#!/bin/bash -xe

python setup.py build_ext -i

export LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libasan.so.5	# XXX debug with asan
python -m pytest "$@"
#gdb python --args python -m pytest "$@"
