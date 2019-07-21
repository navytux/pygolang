#!/bin/bash -xe

python setup.py build_ext -i
python -m pytest "$@"
