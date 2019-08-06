from golang._g import printg, call_using_cstack

c = chan()
def _():
    printg('g1')
    q = chan()
    def aaa():
        printg('g2')
        q.close()
    def bbb():
        go(aaa)
    #bbb()
    call_using_cstack(bbb)
    q.recv()
    c.close()


go(_)
c.recv()
