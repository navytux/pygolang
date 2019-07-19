// XXX COPY

#include <exception>
#include "panic.h"

struct PanicError : std::exception {
	const char *arg;
};

void panic(const char *arg) {
	PanicError _; _.arg = arg;
	throw _;
}

const char *recover() {
	// if PanicError was thrown - recover from it
	try {
		throw;
	} catch (PanicError exc) {
		return exc.arg;
	}

	// XXX other exceptions -> ? handle them or not here?

	return NULL;
}
