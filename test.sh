#!/bin/bash -xe
# build/run pygolang tests in-tree while developing.
# XXX merge into trun?

# distutils takes CFLAGS for both C and C++
# distutils use CFLAGS also at link stage so no need to set LDFLAGS separately
export CFLAGS="-g -O0 -fsanitize=thread"
#export CFLAGS="-g -O0 -fsanitize=address"

python setup.py build_dso -i
python setup.py build_ext -i

#export TSAN_OPTIONS="history_size=7"

./trun python -m pytest "$@"
#./trun gpython -m pytest "$@"
#gdb python -ex run -ex q --args python `which gpython` -m pytest "$@"
