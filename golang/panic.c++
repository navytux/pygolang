// XXX COPY

#include <exception>
#include "panic.h"

struct PanicError : std::exception {
	const char *arg;
};

void panic(const char *arg) {
	throw PanicError{arg};
}
