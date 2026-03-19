print('pkg/__main__')

# imports should be resolved relative current module
from . import mod

# sys.argv
import sys
print(sys.argv)

# variable in module namespace
tag = '~~PKG/MAIN~~'
