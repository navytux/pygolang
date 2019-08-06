from golang._g import printg, call_using_cstack
import time

def usestack_and_call(f, nframes=128):
    if nframes == 0:
        return f()
    return usestack_and_call(f, nframes-1)

def main():
    c = chan()
    def _():
        printg('g2')
        time.sleep(1)   # wait till recv is blocked
        def sss():
            c.send('zzz')
        sss()
        #call_using_cstack(sss)

        #q = chan()
        #def aaa():
        #    printg('g3')
        #    q.send('zzz')
        #go(aaa)
        ##bbb()
        #call_using_cstack(bbb)
        #q.recv()
        #c.close()

    printg('g1')
    go(_)
    def rrr():
        x = c.recv()
        assert x == 'zzz'
    #rrr()
    usestack_and_call(rrr)
    #call_using_cstack(rrr)

    print('ok')


if __name__ == '__main__':
    main()
