#!/usr/bin/env python
# this program shows that the GIL is not locked/unlocked on PyPy:
# Two threads continuosly and concurrenrly access the same dict, whose keys are
# of diffrerent type, and even with `pypy --jit off` there is no many (should
# be proportional to N) calls to sem_wait/sem_post, while with CPython
# sem_wait/sem_post calls ~N are observable.
# Run with `LD_PRELOAD=./sem.so pypy --jit off ./y.py`
# (XXX LD_PRELOAD because ltrace somehow does not work with pypy)
#
# This program was created because pypy-thread-tsan breaks reporting race on
# Py_DECREF of a variable while two threads in question do the inc/dec ref only
# with GIL held.

from __future__ import print_function, absolute_import

import time
#from golang import go, chan
#from golang import time

import sys
sys.setcheckinterval(100)

import thread
def _(): pass
thread.start_new_thread(_, ())
# XXX join
time.sleep(1)

import threading
t = threading.Thread(target=_)
t.start()
t.join()

Z = {-1: 0}

def main():
    global Z
    print('\n\n\nSTART\n\n\n')
    #done = chan()
    def _():
        global Z
        #done.close()
        pass
        for i in range(1000):
            Z[-1] = i
    #go(_)
    #thread.start_new_thread(_, ())
    t = threading.Thread(target=_)
    t.start()
    for i in range(1000):
        _ = Z.setdefault('observed', [])
        l = Z[-1]
        if _ and _[-1] == l:
            continue
        _.append(l)
    print('switched at least #%d times' % len(Z['observed']))
    print(Z)

if __name__ == '__main__':
    main()
