#!/bin/bash -xe

python setup.py build_ext -i
gpython -m pytest -k test_chan golang/golang_test.py
