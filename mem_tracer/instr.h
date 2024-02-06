/*
** instr.h
** Instrumentation to be included by patient code.
**
** You are supossed to:
** - Call "instr_select_next_block()" before the call to malloc/calloc
**   that gives you the block of memory that you want to instrument, so
**   that you "select it" for monitoring.
** - Call "instr_start_tracing()" to start the actual
**   tracing on the selected block of memory.
** - Do your work in that piece of memory...
** - Call "instr_stop_tracing()" to stop the tracing of
**   the selected memory block.
*/

#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>

// __attribute__((optimize("O0"))): Do not optimize away, we need this
// functions to be called

// Tell Pin tool to take note of the memory block reserved by the very
// next malloc/calloc, so that later, start the trace
void __attribute__((optimize("O0")))
instr_select_next_block(void) {}

// starts, from this point, recording all memory accesses to a previously
// selected memory block.
void __attribute__((optimize("O0")))
instr_start_tracing(void) {}

// stops recording memory accesses to a memory block that was previously
// selected and whos access already started to be recorded.
void __attribute__((optimize("O0")))
instr_stop_tracing(void) {}


// aligned allocator
// bytes: writable bytes to request
// alignment: byte alignment. Powers of two accepted. Undefined otherwise
//            For example, if 64 is passed, then make sure that the last
//            6 bits of the pointer returned are 0
void *PTR;
void *aligned_malloc(size_t bytes, size_t alignment){
    size_t ptr_size = sizeof(void*);
    // get space for data, align shift, and to store the real pointer
    void *original_ptr = malloc(bytes + alignment - 1 + ptr_size);

    // align the original pointer. The (uintptr_t*) casting is only to
    // make the next part easier.
    uintptr_t *aligned_ptr = (uintptr_t*)
        (
            // manipulate the address by adding/subtracting bytes
            ((uintptr_t)original_ptr + alignment - 1 + ptr_size)
            & ~(alignment - 1)
        );

    // store original pointer at the left of the aligned pointer
    aligned_ptr[-1] = (uintptr_t)original_ptr;

    PTR = original_ptr;
    char equal = 'N';
    if((void*)aligned_ptr[-1] == original_ptr){
        equal = 'Y';
    }
    printf("%10p %10p %c\n", original_ptr, aligned_ptr, equal);
    if(equal == 'N')
        exit(1);
    return (void*)aligned_ptr;
}

void aligned_free(void *ptr){
    //get the address right at the left of the given pointer
    void *original_ptr = (void *)( ((uintptr_t*)ptr)[-1] );
    printf("%10p\n", original_ptr);
    if(PTR != original_ptr){
        printf("ERROR\n");
        exit(1);
    }

    free(original_ptr);
}
