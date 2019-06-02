// program that imitates python but wraps AST generation so that arbitrary AST
// transform could be hooked in.

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <Python-ast.h>
#include <node.h>

// https://bugs.python.org/issue17515 + PEP 511

// https://stackoverflow.com/q/13961774/9456786
// https://stackoverflow.com/questions/32015082/msvc-linker-equivalent-of-wrap

// -Wl,-wrap,_PyAST_Optimize
int
__real__PyAST_Optimize(mod_ty mod, PyArena *arena, int optimize);

int
__wrap__PyAST_Optimize(mod_ty mod, PyArena *arena, int optimize) {
	printf("AST optimize...\n");
	return __real__PyAST_Optimize(mod, arena, optimize);
}

int
main(int argc, char *argv[])
{
    wchar_t *program = Py_DecodeLocale(argv[0], NULL);
    if (program == NULL) {
        fprintf(stderr, "Fatal error: cannot decode argv[0]\n");
        exit(1);
    }
    Py_SetProgramName(program);  /* optional but recommended */
    Py_Initialize();
    PyRun_SimpleString("from time import time,ctime\n"
                       "print('Today is', ctime(time()))\n");
    if (Py_FinalizeEx() < 0) {
        exit(120);
    }
    PyMem_RawFree(program);
    return 0;
}
