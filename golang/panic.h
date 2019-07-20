#ifndef	_PYGOLANG_PANIC_H
#define	_PYGOLANG_PANIC_H

// XXX COPY

#ifdef	__cplusplus
extern "C" {
#endif

void panic(const char *arg);
const char *recover();
void bug(const char *arg);

#ifdef __cplusplus
}
#endif

#endif	// _PYGOLANG_PANIC_H
