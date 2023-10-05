// Copyright (C) 2023  Nexedi SA and Contributors.
//                     Kirill Smelkov <kirr@nexedi.com>
//
// This program is free software: you can Use, Study, Modify and Redistribute
// it under the terms of the GNU General Public License version 3, or (at your
// option) any later version, as published by the Free Software Foundation.
//
// You can also Link and Combine this program with other software covered by
// the terms of any of the Free Software licenses or any of the Open Source
// Initiative approved licenses and Convey the resulting work. Corresponding
// source of such a combination shall include the source code for all other
// software used.
//
// This program is distributed WITHOUT ANY WARRANTY; without even the implied
// warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
//
// See COPYING file for full licensing terms.
// See https://www.nexedi.com/licensing for rationale and options.

// _golang_str_pickle.S complements _golang_str_pickle.pyx with assembly routines.

#include "golang/runtime/platform.h"

    .text
    .p2align 4

// CSYM returns assembler symbol for C-symbol name
#if defined(LIBGOLANG_OS_darwin) || \
    (defined(LIBGOLANG_OS_windows) && defined(LIBGOLANG_ARCH_386))
# define CSYM(name)  _ ## name
#else
# define CSYM(name)       name
#endif

// _TYPE emits `.type sym, symtype` on systems where .type directive is supported
// _SIZE emits `.size sym, symsize` on systems where .size directive is supported
#ifdef LIBGOLANG_OS_linux
# define _TYPE(sym, symtype) .type sym, symtype
# define _SIZE(sym, symsize) .size sym, symsize
#else
# define _TYPE(sym, type)
# define _SIZE(sym, size)
#endif

// inside_counted provides trampoline to call *inside_counted_func with
// counting how many times that function entered inside and exited.
//
// Each enter increments inside_counter, while each exit decrements it.
// Recursion is supported up to STK_SIZE times with counter stopping to be
// adjusted at deeper recursion levels.
//
// inside_counted can be used on functions with arbitrary signatures because
// all registers and stack arguments are preserved exactly as is on the call(*).
//
// (*) NOTE₁ on-stack return address / link-register is adjusted during the call.
//           this prevents inside_counted to be used with e.g. x86.get_pc_thunk.ax .
//     NOTE₂ on ARM64 xip0 (x16) is clobbered.
#define inside_counted          CSYM(inside_counted)
#define inside_counted_func     CSYM(inside_counted_func)
#define inside_counter          CSYM(inside_counter)
#define inside_counted_stk      CSYM(inside_counted_stk)
    .globl  inside_counted
    _TYPE(  inside_counted, @function   )
inside_counted:
#define STK_SIZE 8

// ---- X86_64 / i386 ----

#if defined(LIBGOLANG_ARCH_amd64) || defined(LIBGOLANG_ARCH_386)
#if defined(LIBGOLANG_ARCH_amd64)
# define REGSIZE  8
# define rAX    rax
# define rPCNT  rbx
# define rCNT   rcx
# define rPSTK  rdx
# define rSP    rsp
# ifndef LIBGOLANG_OS_windows
   .macro LEAGOT sym, reg
     movq   \sym@GOTPCREL(%rip), %\reg
   .endm
# else
   // windows does not use PIC and relocates DLLs when loading them
   // there is no GOT and we need to access in-DLL symbols directly
   // see e.g. https://stackoverflow.com/q/13309662/9456786 for details.
   .macro LEAGOT sym, reg
     leaq   \sym(%rip), %\reg   // NOTE pc-relative addressing used to avoid LNK2017:
   .endm                        // 'ADDR32' relocation ... invalid without /LARGEADDRESSAWARE:NO
# endif
#else
# define REGSIZE  4
# define rAX    eax
# define rPCNT  ebx
# define rCNT   ecx
# define rPSTK  edx
# define rSP    esp
# ifndef LIBGOLANG_OS_windows
   .macro LEAGOT sym, reg
     call   .Lget_pc_\reg
     addl   $_GLOBAL_OFFSET_TABLE_, %\reg
     movl   \sym@GOT(%\reg), %\reg
   .endm
# else
   // windows does not use PIC - see details in ^^^ amd64 case
   .macro LEAGOT sym, reg
     leal \sym, %\reg
   .endm
# endif
#endif

    sub     $REGSIZE, %rSP    // make place for jmp-via-ret to *inside_counted_func

    // TODO consider adding cfi_* annotations, but probably it won't be simple
    //      since we manipulate retaddr on the stack

    push    %rAX        // save registers we'll use
    push    %rPCNT
    push    %rCNT
    push    %rPSTK
#define SP_JMPVIARET    (4*REGSIZE)
#define SP_RETORIG      (5*REGSIZE)

    // jmp-via-ret = *inside_counted_func
    LEAGOT  inside_counted_func, rAX                    // &inside_counted_func
    mov     (%rAX), %rAX                                //  inside_counted_func
    mov     %rAX, SP_JMPVIARET(%rSP)

    // check whether altstk is overflowed
    // if it is - invoke the func without counting
    LEAGOT  inside_counter, rPCNT                       // &inside_counter
    mov     (%rPCNT), %rCNT                             //  inside_counter
    cmp     $STK_SIZE, %rCNT
    jge     .Lcall

    // altstk is not overflowed
    // push original ret to altstk and replace the ret to return to us after the call
    LEAGOT  inside_counted_stk, rPSTK                   // &inside_counted_stk
    mov     SP_RETORIG(%rSP), %rAX                      // original ret address
    mov     %rAX, (%rPSTK,%rCNT,REGSIZE)                // inside_counted_stk[inside_counter] = retorig
    add     $1, %rCNT                                   // inside_counter++
    mov     %rCNT, (%rPCNT)

#if defined(LIBGOLANG_ARCH_amd64)
    lea     .Laftercall(%rip), %rAX
#else
    call    .Lget_pc_eax
    add     $(.Laftercall-.), %rAX
#endif
    mov     %rAX, SP_RETORIG(%rSP)                      // replace ret addr on stack to .Laftercall

.Lcall:
    // restore registers and invoke the func through jmp-via-ret
    pop     %rPSTK
    pop     %rCNT
    pop     %rPCNT
    pop     %rAX
    ret

.Laftercall:
    // we get here after invoked func returns if altstk was not overflowed
    // decrement inside_counter and return to original ret address
    sub     $REGSIZE, %rSP  // make place for original ret
    push    %rAX            // save registers
    push    %rPCNT
    push    %rCNT
    push    %rPSTK
#undef  SP_RETORIG
#define SP_RETORIG      (4*REGSIZE)

    LEAGOT  inside_counter, rPCNT                       // &inside_counter
    mov     (%rPCNT), %rCNT                             //  inside_counter
    sub     $1, %rCNT
    mov     %rCNT, (%rPCNT)                             //  inside_counter--
    LEAGOT  inside_counted_stk,  rPSTK                  // &inside_counted_stk
    mov     (%rPSTK,%rCNT,REGSIZE), %rAX                // retorig = inside_counted_stk[inside_counter]
    mov     %rAX, SP_RETORIG(%rSP)

    // restore registers and return to original caller
    pop     %rPSTK
    pop     %rCNT
    pop     %rPCNT
    pop     %rAX
    ret

#if defined(LIBGOLANG_ARCH_386)
.macro DEF_get_pc reg
 .Lget_pc_\reg:
    mov     (%esp), %\reg
    ret
.endm
DEF_get_pc eax
DEF_get_pc ebx
DEF_get_pc ecx
DEF_get_pc edx
#endif

// ---- ARM64 ----

#elif defined(LIBGOLANG_ARCH_arm64)
#define REGSIZE 8
#define rPCNT   x0
#define rCNT    x1
#define rPSTK   x2
#define rXIP0   x16
    stp     rPCNT, rCNT, [sp, -16]!     // save registers we'll use
    stp     rPSTK, xzr,  [sp, -16]!     // NOTE xip0 is clobbered

    // xip0 = *inside_counted_func
    adrp    rXIP0, :got:inside_counted_func
    ldr     rXIP0, [rXIP0, :got_lo12:inside_counted_func]   // &inside_counted_func
    ldr     rXIP0, [rXIP0]                                  //  inside_counted_func

    // check whether altstk is overflowed
    // if it is - invoke the func without counting
    adrp    rPCNT, :got:inside_counter
    ldr     rPCNT, [rPCNT, :got_lo12:inside_counter]        // &inside_counter
    ldr     rCNT, [rPCNT]                                   //  inside_counter
    cmp     rCNT, STK_SIZE
    bge     .Lcall

    // altstk is not overflowed
    // push original ret to altstk and replace the ret to return to us after the call
    adrp    rPSTK, :got:inside_counted_stk
    ldr     rPSTK, [rPSTK, :got_lo12:inside_counted_stk]    // &inside_counted_stk
    str     lr, [rPSTK, rCNT, lsl 3]                        // inside_counted_stk[inside_counter] = retorig
    add     rCNT, rCNT, 1                                   // inside_counter++
    str     rCNT, [rPCNT]

    adr     lr, .Laftercall                                 // replace ret addr to .Laftercall

.Lcall:
    // restore registers and invoke the func via xip0
    ldp     rPSTK, xzr,  [sp], 16
    ldp     rPCNT, rCNT, [sp], 16
    br      rXIP0

.Laftercall:
    // we get here after invoked func returns if altstk was not overflowed
    // decrement inside_counter and return to original ret address
    stp     rPCNT, rCNT, [sp, -16]!     // save registers
    stp     rPSTK, xzr,  [sp, -16]!

    adrp    rPCNT, :got:inside_counter
    ldr     rPCNT, [rPCNT, :got_lo12:inside_counter]        // &inside_counter
    ldr     rCNT, [rPCNT]                                   //  inside_counter
    sub     rCNT, rCNT, 1
    str     rCNT, [rPCNT]                                   //  inside_counter--
    adrp    rPSTK, :got:inside_counted_stk
    ldr     rPSTK, [rPSTK, :got_lo12:inside_counted_stk]    // &inside_counted_stk
    ldr     lr, [rPSTK, rCNT, lsl 3]                        // lr = inside_counted_stk[inside_counter]

    // restore registers and return to original caller
    ldp     rPSTK, xzr,  [sp], 16
    ldp     rPCNT, rCNT, [sp], 16
    ret

#else
# error "unsupported architecture"
#endif

    _SIZE(  inside_counted, .-inside_counted    )

// ---- data ---
    .bss

// void* inside_counted_func
    .globl  inside_counted_func
    .p2align 3  // 8
    _TYPE(  inside_counted_func, @object    )
    _SIZE(  inside_counted_func, REGSIZE    )
inside_counted_func:
    .zero   REGSIZE

// long inside_counter
    .globl  inside_counter
    .p2align 3  // 8
    _TYPE(  inside_counter, @object )
    _SIZE(  inside_counter, REGSIZE )
inside_counter:
    .zero   REGSIZE

// void* inside_counted_stk[STK_SIZE]
    .globl  inside_counted_stk
    .p2align 5  // 32
    _TYPE(  inside_counted_stk, @object             )
    _SIZE(  inside_counted_stk, STK_SIZE*REGSIZE    )
inside_counted_stk:
    .zero   STK_SIZE*REGSIZE


// disable executable stack
#ifndef LIBGOLANG_OS_windows
    .section        .note.GNU-stack,"",@progbits
#endif


// ---- custom callconv proxies ----
    .text
    .p2align 4

// saveprobe_<callconv>            (self, obj, pers_save)  input callconv, proxy to saveprobe
// _pickle_Pickler_xsave_<callconv>(self, obj, pers_save)  input callconv, proxy to _pickle_Pickler_xsave
// save_invoke_as_<callconv> (save, self, obj, pers_save)  input std, proxy to save invoked via callconv


#if defined(LIBGOLANG_ARCH_386)

#ifdef LIBGOLANG_CC_msc
# define CSYM_FASTCALL3(name)   @name@12     // MSVC mangles __fastcall
# define CSYM_FASTCALL4(name)   @name@16
#else
# define CSYM_FASTCALL3(name)   CSYM(name)
# define CSYM_FASTCALL4(name)   CSYM(name)
#endif

// python-3.11.5.exe has _pickle.save accepting arguments in ecx,edx,stack but
// contrary to fastcall the callee does not cleanup the stack.
// Handle this as fastcall_nostkclean

.macro FUNC_fastcall_nostkclean name
    .globl  CSYM(\name\()_fastcall_nostkclean)
    _TYPE(  CSYM(\name\()_fastcall_nostkclean), @function    )
CSYM(\name\()_fastcall_nostkclean):
    // we are proxying to fastcall - ecx and edx are already setup and we
    // need to only duplicate the 3rd argument on the stack. Do this without
    // clobbering any register.
    sub     $4, %esp        // place to copy on-stack argument to
    push    %eax
    mov     12(%esp), %eax  // original on-stack arg
    mov     %eax, 4(%esp)   // dup to copy
    pop     %eax

    call    CSYM_FASTCALL3(\name\()_ifastcall)
    // ^^^ cleaned up the stack from our copy
    // nothing to do anymore
    ret
    _SIZE(  CSYM(\name\()_fastcall_nostkclean), .-CSYM(\name\()_fastcall_nostkclean)  )
.endm
FUNC_fastcall_nostkclean  saveprobe
FUNC_fastcall_nostkclean  _pickle_Pickler_xsave
FUNC_fastcall_nostkclean  _zpickle_Pickler_xsave

#define save_invoke_as_fastcall_nostkclean  CSYM_FASTCALL4(save_invoke_as_fastcall_nostkclean)
    .globl  save_invoke_as_fastcall_nostkclean
    _TYPE(  save_invoke_as_fastcall_nostkclean, @function   )
save_invoke_as_fastcall_nostkclean:
    // input:
    //      ecx:     save
    //      edx:     self
    //      stk[1]:  obj
    //      stk[2]:  pers_save
    //
    // invoke save as:
    //      ecx:     self
    //      edx:     obj
    //      stk*[1]: pers_save

    mov     8(%esp), %eax       // pers_save
    push    %eax                // stk*[1] <- per_save

    mov     %ecx, %eax          // eax <- save
    mov     %edx, %ecx          // ecx <- self
    mov     (4+4)(%esp), %edx   // edx <- obj

    call    *%eax

    // return with cleaning up stack
    add     $4, %esp    // pers_save copy we created
    ret     $8          // original arguments
    _SIZE(  save_invoke_as_fastcall_nostkclean, .-save_invoke_as_fastcall_nostkclean)

#endif  // 386
