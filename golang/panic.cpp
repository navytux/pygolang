// XXX COPY

#include <exception>
#include <string>
#include "panic.h"

using std::string;
using std::exception;

struct PanicError : exception {
	const char *arg;
};

void panic(const char *arg) {
	PanicError _; _.arg = arg;
	throw _;
}

// recover recovers from exception thrown by panic.
// it returns: !NULL - there was panic with that argument. NULl - there was no panic.
// if another exception was thrown - recover rethrows it.
const char *recover() {
	// if PanicError was thrown - recover from it
	try {
		throw;
	} catch (PanicError &exc) {
		return exc.arg;
	}

	return NULL;
}


// bug indicates internl bug in golang implementation.
struct Bug : exception {
	const string msg;

	virtual const char *what() const throw() {
		return msg.c_str();
	}

	Bug(const string &msg) : msg("BUG: " + msg) {}
};

void bug(const char *msg) {
	throw Bug(msg);
}
