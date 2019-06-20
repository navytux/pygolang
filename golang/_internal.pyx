# cython: language_level=2

# bytepatch does `mem[i]=b` even for read-only mem object such as bytes.
def bytepatch(const unsigned char[::1] mem not None, int i, unsigned char b):
    # we don't care if its readonly or writeable buffer - we change it anyway
    cdef unsigned char *xmem = <unsigned char *>&mem[0]
    assert 0 <= i < len(mem)
    xmem[i] = b
