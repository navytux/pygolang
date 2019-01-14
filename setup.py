# pygolang | pythonic package setup
from setuptools import setup, find_packages
from os.path import dirname, join
import re

# read file content
def readfile(path):
    with open(path, 'r') as f:
        return f.read()

# grep searches text for pattern.
# return re.Match object or raises if pattern was not found.
def grep1(pattern, text):
    rex = re.compile(pattern, re.MULTILINE)
    m = rex.search(text)
    if m is None:
        raise RuntimeError('%r not found' % pattern)
    return m

# find our version
_ = readfile(join(dirname(__file__), 'golang/__init__.py'))
_ = grep1('^__version__ = "(.*)"$', _)
version = _.group(1)

setup(
    name        = 'pygolang',
    version     = version,
    description = 'Go-like features for Python',
    long_description = '%s\n----\n\n%s' % (
                            readfile('README.rst'), readfile('CHANGELOG.rst')),
    url         = 'https://lab.nexedi.com/kirr/pygolang',
    license     = 'GPLv3+ with wide exception for Open-Source',
    author      = 'Kirill Smelkov',
    author_email= 'kirr@nexedi.com',

    keywords    = 'go channel goroutine GOPATH python import',

    packages    = find_packages(),

    install_requires = ['six', 'decorator'],

    extras_require = {
                  'test': ['pytest'],
    },

    entry_points= {'console_scripts': [
                        'py.bench = golang.cmd.pybench:main',
                      ]
                  },

    classifiers = [_.strip() for _ in """\
        Development Status :: 3 - Alpha
        Intended Audience :: Developers
        Programming Language :: Python :: 2
        Programming Language :: Python :: 3\
    """.splitlines()]
)
