#!/bin/bash -xe

python setup.py build_ext -i
python -m pytest "$@"
#gdb python --args python -m pytest "$@"
