// gcc -Wall -shared -fPIC sem.c -o sem.so
#define	_GNU_SOURCE 1
#define	GNU_SOURCE 1
#include <stdio.h>
#include <dlfcn.h>
#include <sys/types.h>
#include <unistd.h>
#include <sys/syscall.h>

pid_t gettid() {
	return syscall(SYS_gettid);
}

typedef struct sem_t sem_t;

int (*_sem_wait)(sem_t *) = NULL;
int sem_wait(sem_t *sem) {
	fprintf(stderr, "%d: sem_wait %p\n", gettid(), sem);
	fflush(stderr);
	if (!_sem_wait) {
		_sem_wait = dlsym(RTLD_NEXT, "sem_wait");
	}
	return _sem_wait(sem);
}

int (*_sem_post)(sem_t *) = NULL;
int sem_post(sem_t *sem) {
	fprintf(stderr, "%d: sem_post %p\n", gettid(), sem);
	fflush(stderr);
	if (!_sem_post) {
		_sem_post = dlsym(RTLD_NEXT, "sem_post");
	}
	return _sem_post(sem);
}
