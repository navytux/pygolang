#!/bin/bash -xe

#export CFLAGS="-fsanitize=thread"	# distutils take this for both C and C++
export CFLAGS="-g -O0"	# distutils take this for both C and C++
#export CFLAGS="-g -O0 -fsanitize=thread"	# distutils take this for both C and C++
#export CFLAGS="-g -fsanitize=thread"	# distutils take this for both C and C++

#export CFLAGS="-O0 -g -fsanitize=thread"	# distutils take this for both C and C++
#export CFLAGS="-O0 -g -fsanitize=address"	# distutils take this for both C and C++
# distutils use CFLAGS also at link stage so no need to set LDFLAGS separately
#export LDFLAGS="-kirr"

python setup.py build_dso -i

# XXX recheck
# # FIXME why tsan does not detect problems if other extensions are also compiled with -race?
# XXX -> likely change in scheduling
unset CFLAGS

python setup.py build_ext -i

#export TSAN_OPTIONS="history_size=7 force_seq_cst_atomics=1 verbosity=1"
#export TSAN_OPTIONS="history_size=7 verbosity=1"
#export TSAN_OPTIONS="history_size=7"

#LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libasan.so.5 python -m pytest "$@"
./trun python -m pytest "$@"
#./trun gpython -m pytest "$@"
#gdb python -ex run -ex q --args python `which gpython` -m pytest "$@"
