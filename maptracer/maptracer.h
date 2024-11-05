/*
** mem_tracer.h
** Instrumentation to be included by patient code.
**
** You are supossed to:
** - Call "mt_select_next_block()" before the call to malloc/calloc
**   that gives you the block of memory that you want to instrument, so
**   that you "select it" for monitoring.
** - Call "mt_start_tracing()" to start the actual
**   tracing on the selected block of memory.
** - Do your work in that piece of memory...
** - Call "mt_stop_tracing()" to stop the tracing of
**   the selected memory block.
*/

#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>

// __attribute__((optimize("O0"))): Do not optimize away, we need this
// functions to be called

// Tell Pin tool to take note of the memory block reserved by the very
// next malloc/calloc, so that later, start the trace
#if defined(__GNUC__) && !defined(__clang__)
void __attribute__((optimize("O0"))) mt_select_next_block(void) {}
#else
void __attribute__((noinline, used)) mt_select_next_block(void) {}
#endif

// starts, from this point, recording all memory accesses to a previously
// selected memory block.
#if defined(__GNUC__) && !defined(__clang__)
void __attribute__((optimize("O0"))) mt_start_tracing(void) {}
#else
void __attribute__((noinline, used)) mt_start_tracing(void) {}
#endif

// stops recording memory accesses to a memory block that was previously
// selected and whos access already started to be recorded.
#if defined(__GNUC__) && !defined(__clang__)
void __attribute__((optimize("O0"))) mt_stop_tracing(void) {}
#else
void __attribute__((noinline, used)) mt_stop_tracing(void) {}
#endif


// Aligned Memory Allocator: gets a block of memory where the first byte
// of the returned address is aligned to blocks of <alignment> bytes.
// So for example, if 64 is passed, then make sure that the last 6 bytes
// of the returned pointer are 0. ONLY Powers of two accepted. Undefined
// otherwise.
//
// Arguments:
//     bytes     : Number of writable bytes to request
//     alignment : Number of bytes to align the block.
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

    return (void*)aligned_ptr;
}

void aligned_free(void *ptr){
    //get the address right at the left of the given pointer
    void *original_ptr = (void *)( ((uintptr_t*)ptr)[-1] );
    free(original_ptr);
}
