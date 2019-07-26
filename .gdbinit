#set args -m pytest -s bigfile/tests/test_1.py
#set args -m pytest --ignore=3rdparty --ignore=build --ignore=t -v -s
#set args ./demo-2ram.py
#handle SIGSEGV noprint nostop
#b pybigfile_loadblk


# print python-level backtrace to program stdout from-under gdb
define xpybt
    set $_gstate = PyGILState_Ensure()
    set $_unused_int  = PyRun_SimpleString("import traceback; traceback.print_stack()")
    set $_unused_void = PyGILState_Release($_gstate)
end
