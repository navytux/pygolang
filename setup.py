# pygopath | pythonic package setup
from setuptools import setup, find_packages

# read file content
def readfile(path):
    with open(path, 'r') as f:
        return f.read()

setup(
    name        = 'pygopath',
    version     = '0.0.0.dev1',
    description = 'Import python modules by full-path in Go workspace',
    long_description = readfile('README.rst'),
    url         = 'https://lab.nexedi.com/kirr/pygopath',
    license     = 'GPLv3+ with wide exception for Open-Source',
    author      = 'Kirill Smelkov',
    author_email= 'kirr@nexedi.com',

    keywords    = 'go GOPATH python import',

    # XXX find_packages does not find top-level *.py
    #packages    = find_packages(),
    packages    = [''],

    extras_require = {
                  'test': ['pytest'],
    },

    classifiers = [_.strip() for _ in """\
        Development Status :: 3 - Alpha
        Intended Audience :: Developers\
    """.splitlines()]
)
