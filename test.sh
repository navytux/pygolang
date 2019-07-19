#!/bin/bash -xe

python setup.py build_ext -i
python -m pytest -k test_chan golang/golang_test.py
