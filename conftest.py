# ignore tests in distorm - else it breaks as e.g.
#
# 3rdparty/funchook/distorm/python/test_distorm3.py:15: in <module>
#     import distorm3
# 3rdparty/funchook/distorm/python/distorm3/__init__.py:57: in <module>
#     _distorm = _load_distorm()
# 3rdparty/funchook/distorm/python/distorm3/__init__.py:55: in _load_distorm
#     raise ImportError("Error loading the diStorm dynamic library (or cannot load library into process).")
# E   ImportError: Error loading the diStorm dynamic library (or cannot load library into process).
collect_ignore = ["3rdparty"]
