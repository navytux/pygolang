print('dir/__main__')

# imports should be resolved relative to dir
import mod

# sys.argv
import sys
print(sys.argv)

# variable in module namespace
tag = '~~DIR/MAIN~~'
