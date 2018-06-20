# pygolang | pythonic package setup
from setuptools import setup, find_packages

# read file content
def readfile(path):
    with open(path, 'r') as f:
        return f.read()

setup(
    name        = 'pygolang',
    version     = '0.0.0.dev2',
    description = 'Go-like features for Python',
    long_description = readfile('README.rst'),
    url         = 'https://lab.nexedi.com/kirr/pygolang',
    license     = 'GPLv3+ with wide exception for Open-Source',
    author      = 'Kirill Smelkov',
    author_email= 'kirr@nexedi.com',

    keywords    = 'go channel goroutine GOPATH python import',

    packages    = find_packages(),

    extras_require = {
                  'test': ['pytest'],
    },

    classifiers = [_.strip() for _ in """\
        Development Status :: 3 - Alpha
        Intended Audience :: Developers\
    """.splitlines()]
)
