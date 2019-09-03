#!/bin/bash -xe

python setup.py build_dso -i
python setup.py build_ext -i

./trun python -m pytest "$@"
./trun gpython -m pytest "$@"
#gdb python -ex run -ex q --args python `which gpython` -m pytest "$@"

#gpython g.py
