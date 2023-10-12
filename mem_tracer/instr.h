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
