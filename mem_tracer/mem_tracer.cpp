/* mem_tracer.cpp
 *
 * Copyright (C) 2004-2021 Intel Corporation.
 * Copyright (C) 2023 Marco Bonelli.
 * Copyright (C) 2023 Claudio Parra.
 * SPDX-License-Identifier: MIT.
 *
 * This pintool with the header instr.h provides a tool to select a block of
 * memory allocated with malloc() (not working for calloc), and trace all
 * accesses to such memory block. The tool records:
 *  - the kind of access (R for read, W for write).
 *  - the size of the read/write (in bytes).
 *  - the offset from the beginning of the block (in bytes).
 * The trace is stored in a file called (by default) "mem_trace_log.out"
 */

#include "pin.H"
#include <iostream>
#include <fstream>

// data structure to keep the information of the memory block being tracked
struct tracked_malloc_block {
    ADDRINT start;     // First address of the block
    ADDRINT end;       // Last address of the block
    ADDRINT size;      // The size of the block in bytes
    bool being_traced; // Whether this block is currently being traced.
                       // This value is false until action_start_tracing()
                       // is called.
};

// defined to make sure "select block", "malloc before", and "malloc after" are
// called in exactly that order.
enum SEL_BLOCK{NO_SELECTION, PRE_BEF_MALLOC, POST_BEF_MALLOC};


// whether to select the next allocated block (through malloc) for tracing.
// It has three values:
//   0: do not pay attention to the next malloc.
//   1: pay attention to the next malloc. Function malloc_before has not
//      ran yet. Only accepted value for malloc_before to run.
//   2: malloc found, and malloc_before has ran. Only accepted value for
//      malloc_after to run.
// So the cycle is: 0 -> select -> 1 -> malloc_before -> 2 -> malloc_after -> 0
SEL_BLOCK select_next_block = NO_SELECTION;

// file where to store all the analysis made by this tool.
std::ofstream trace_file;

// this lock serializes the access to the output file (trace_file)
PIN_LOCK pin_lock;

// data structure to keep the information of the memory block being tracked.
struct tracked_malloc_block tracked_block
    = {.start=0, .end=0, .size=0, .being_traced=false};

// option for the pin command line tool. In this case: '-o output_filename'.
// Its default value is 'mem_trace_log.out'
KNOB<std::string> trace_output_fname(
    KNOB_MODE_WRITEONCE, "pintool", "o",
    "mem_trace_log.out", "specify trace file name");




/* ==============================================================
 *   Analysis Routines
 * ==============================================================
 *  Note:  threadid+1 is used as an argument to the PIN_GetLock()
 *         routine as a debugging aid.  This is the value that
 *         the lock is set to, so it must be non-zero. */
/* This routine is called every time a thread is created */
VOID thread_start(THREADID threadid, CONTEXT* ctxt, INT32 flags, VOID* v){
    if(threadid == 0)
        return;

    PIN_GetLock(&pin_lock, threadid + 1);
    trace_file
        << threadid << ","
        << "Tc,"
        << "0,"
        << "0" << std::endl;
    PIN_ReleaseLock(&pin_lock);
}

/* This routine is called every time a thread is destroyed. */
VOID thread_end(THREADID threadid, const CONTEXT* ctxt, INT32 code, VOID* v){
    if(threadid == 0)
        return;

    PIN_GetLock(&pin_lock, threadid + 1);
    trace_file
        << threadid << ","
        << "Td,"
        << "0,"
        << "0" << std::endl;
    PIN_ReleaseLock(&pin_lock);
}



/* Sets flag such that the next time the pintool calls malloc_before(),
 * the size given to malloc is recorded */
VOID action_select_next_block(){
    select_next_block = PRE_BEF_MALLOC;
}

/* Executed *before* a malloc() call: save block size. */
VOID malloc_before(ADDRINT size) {
    // if action_select_next_block has not ran yet, abort.
    if (select_next_block != PRE_BEF_MALLOC)
        return;
    select_next_block = POST_BEF_MALLOC;
    tracked_block.size = size;
}

/* Executed *after* a malloc() call: save the allocated block's start and
 * end addresses */
VOID malloc_after(ADDRINT retval, THREADID threadid) {
    PIN_GetLock(&pin_lock, threadid + 1);
    // if malloc_before has not ran yet, abort.
    if (select_next_block != POST_BEF_MALLOC){
        PIN_ReleaseLock(&pin_lock);
        return;
    }

    // if malloc failed to allocate a block of memory.
    if (retval == 0) {
        trace_file << "ERROR: malloc() failed and returned 0!" << std::endl;
        PIN_ReleaseLock(&pin_lock);
        return;
    }
    tracked_block.start = retval;
    tracked_block.end = retval + tracked_block.size;

    // if patient called malloc() requesting a block of size 0.
    if (!tracked_block.size) {
        trace_file << "ERROR: Was malloc() called with argument 0? "
                   << "Block of size zero. Nothing to trace." << std::endl;
        PIN_ReleaseLock(&pin_lock);
        return;
    }

    // log to file
    trace_file << std::hex << std::showbase
               << "START_ADDR   : " << tracked_block.start << std::endl
               << "END_ADDR     : " << tracked_block.end   << std::endl
               << std::noshowbase << std::dec
               << "SIZE_BYTES   : " << tracked_block.size  << std::endl
               << "ALLOCATED_BY : thread " << threadid     << std::endl
               << std::endl
               << "TRACE_DATA_START" << std::endl;
    trace_file << "thread,action,size,offset" << std::endl;

    // reset flag so following mallocs are not tracked.
    select_next_block = NO_SELECTION;
    PIN_ReleaseLock(&pin_lock);
}

// NOTE: record the barriers so I can "re-sync" the x-possition of all threads
// accesses from the perspective of the one calling the sync. This will avoid
// the apparent trans-barrier data overlap. it would be neat to draw it...


/* If a block is not being traced, then start tracing it. */
VOID action_start_tracing(THREADID threadid){
    PIN_GetLock(&pin_lock, threadid + 1);
    // if we are ALREADY tracing, then there is nothing to do.
    if (tracked_block.being_traced){
        PIN_ReleaseLock(&pin_lock);
        return;
    }

    // if there is no block to trace, or its size is zero
    if (!tracked_block.start || !tracked_block.size) {
        trace_file << "Block start: " << tracked_block.start << std::endl
                   << "Block size : " << tracked_block.size << std::endl;
        trace_file << "ERROR: Cannot start tracing without having allocated "
                   << "a block of memory. Did you call instr_select_next_block() "
                   << "before the malloc() that reserves the block that you want "
                   << "to trace?" << std::endl;
        PIN_ReleaseLock(&pin_lock);
        return;
    }
    tracked_block.being_traced = true;
    PIN_ReleaseLock(&pin_lock);
}

/* If a block is being traced, then stop tracing it. */
VOID action_stop_tracing(){
    // if we are not tracing, then there is nothing to do.
    if (!tracked_block.being_traced)
        return;
    // clears tracked memory block, so future R/W instructions don't
    // record anything on the trace file.
    tracked_block = {.start=0, .end=0, .size=0, .being_traced=false};
}

/* Executed *before* a free() call: if the freed block is being traced,
 * then stop the trace. */
VOID free_before(ADDRINT addr, THREADID threadid) {
    // if free was called upon the tracked memory block, then stop tracing.
    PIN_GetLock(&pin_lock, threadid + 1);
    if (tracked_block.being_traced == true && addr == tracked_block.start){
        action_stop_tracing();
        trace_file << "Trace stopped. free("
                   << std::hex << std::showbase
                   << addr
                   << std::noshowbase << std::dec
                   << ") called by thread " << threadid
                   << "." << std::endl;
    }
    PIN_ReleaseLock(&pin_lock);
}



/* Executed *before* any read operation: registers address and read size */
VOID trace_read_before(ADDRINT ip, ADDRINT addr, UINT32 size, THREADID threadid) {
    // if we are tracing nothing, or reading nothing, or reading before or after
    // the monitored block; then do nothing.
    ADDRINT offset = addr - tracked_block.start;
    if (!tracked_block.being_traced || !tracked_block.size || !size ||
        offset < 0 || offset >= tracked_block.size)
        return;

    PIN_GetLock(&pin_lock, threadid + 1);
    trace_file
        << threadid << ","
        << "R,"
        << size << ","
        << offset << std::endl;
    PIN_ReleaseLock(&pin_lock);
}

/* Executed *before* any write operation: registers address and write size */
VOID trace_write_before(ADDRINT ip, ADDRINT addr, UINT32 size, THREADID threadid) {

    // if we are tracing nothing, or writing nothing, or writing before or after
    // the monitored block; then do nothing.
    ADDRINT offset = addr - tracked_block.start;
    if (!tracked_block.being_traced || !tracked_block.size || !size ||
        offset < 0 || offset >= tracked_block.size)
        return;

    PIN_GetLock(&pin_lock, threadid + 1);
    trace_file
        << threadid << ","
        << "W,"
        << size << ","
        << offset << std::endl;
    PIN_ReleaseLock(&pin_lock);
}




/* ====================================================================
 * Instrumentation Routines
 * ==================================================================== */

/* "Modify" the binary image, so that new routines can be injected before and
 * after certain routines originally in the image. */
VOID image_load(IMG img, VOID* v) {
    // The concept of "Instrumenting a function" is like "tampering" the
    // execution of a given function. So another function can run before or
    // after it.

    // Instrument the flag-functions present in the patient code.
    // - inst_select_next_block
    // - instr_start_tracing
    // - instr_stop_tracing
    //
    // Just before the function patient calls instr_select_next_block(),
    // the pintool will call action_select_next_block().
    RTN select_routine = RTN_FindByName(img, "instr_select_next_block");
    if (RTN_Valid(select_routine)) {
        RTN_Open(select_routine);
        RTN_InsertCall(select_routine,
                       IPOINT_BEFORE,
                       (AFUNPTR)action_select_next_block,
                       IARG_END);
        RTN_Close(select_routine);
    }
    // The same idea applies for patient's functions instr_start_tracing()
    // and instr_stop_tracing().
    RTN start_routine = RTN_FindByName(img, "instr_start_tracing");
    if (RTN_Valid(start_routine)) {
        RTN_Open(start_routine);
        RTN_InsertCall(start_routine,
                       IPOINT_BEFORE,
                       (AFUNPTR)action_start_tracing,
                       // pass Pin-Thread ID
                       IARG_THREAD_ID,
                       IARG_END);
        RTN_Close(start_routine);
    }
    RTN stop_routine = RTN_FindByName(img, "instr_stop_tracing");
    if (RTN_Valid(stop_routine)) {
        RTN_Open(stop_routine);
        RTN_InsertCall(stop_routine,
                       IPOINT_BEFORE,
                       (AFUNPTR)action_stop_tracing,
                       IARG_END);
        RTN_Close(stop_routine);
    }

    // Instrument malloc() to save the address and size of the block.
    // Note that this instrumentation happens for any malloc in the
    // patient code, but given the definitions of "malloc_before" and
    // "malloc_after", stuff only happens when the patient has
    // previously called "instr_select_next_block".
    RTN malloc_routine = RTN_FindByName(img, "malloc");
    if (RTN_Valid(malloc_routine)) {
        RTN_Open(malloc_routine);
        RTN_InsertCall(malloc_routine,
                       IPOINT_BEFORE,
                       (AFUNPTR)malloc_before,
                       // pass the value of the 0th argument of
                       // malloc() to malloc_before()
                       IARG_FUNCARG_ENTRYPOINT_VALUE, 0,
                       IARG_END);
        RTN_InsertCall(malloc_routine,
                       IPOINT_AFTER,
                       (AFUNPTR)malloc_after,
                       // pass the return value of malloc() to
                       // malloc_after()
                       IARG_FUNCRET_EXITPOINT_VALUE,
                       // pass a Pin-specific thread ID
                       IARG_THREAD_ID,
                       IARG_END);
        RTN_Close(malloc_routine);
    }

    // In case the patient has not called "instr_stop_tracing", anyway
    // stop the tracing if patient code calls "free".
    RTN free_routine = RTN_FindByName(img, "free");
    if (RTN_Valid(free_routine)) {
        RTN_Open(free_routine);
        RTN_InsertCall(free_routine,
                       IPOINT_BEFORE,
                       (AFUNPTR)free_before,
                       // pass the zero-th argument's value of free() to
                       // free_before()
                       IARG_FUNCARG_ENTRYPOINT_VALUE, 0,
                       // pass a Pin-specific thread ID
                       IARG_THREAD_ID,
                       IARG_END);
        RTN_Close(free_routine);
    }
}

/* "Modify" instructions so that upon detection of certain kind of instructions,
 * extra code could run before or after them. Here, we are tampering all memory
 * read and write instructions */
VOID rw_instructions(INS ins, VOID* v) {
    UINT32 n = INS_MemoryOperandCount(ins);

    for (UINT32 i = 0; i < n; i++) {
        // Instrument read operations to register address and size.
        if (INS_MemoryOperandIsRead(ins, i)) {
            INS_InsertPredicatedCall(
                ins,
                IPOINT_BEFORE,
                (AFUNPTR)trace_read_before,
                IARG_INST_PTR, IARG_MEMORYOP_EA, i,
                IARG_MEMORYOP_SIZE, i,
                // pass a Pin-specific thread ID
                IARG_THREAD_ID,
                IARG_END);
        }

        // Instrument write operations to register address and size.
        if (INS_MemoryOperandIsWritten(ins, i)) {
            INS_InsertPredicatedCall(
                ins,
                IPOINT_BEFORE,
                (AFUNPTR)trace_write_before,
                IARG_INST_PTR, IARG_MEMORYOP_EA, i,
                IARG_MEMORYOP_SIZE, i,
                // pass a Pin-specific thread ID
                IARG_THREAD_ID,
                IARG_END);
        }
    }
}

/* What to do at the end of the execution. */
VOID Fini(INT32 code, VOID* v) {
    trace_file.close();
}




/* =====================================================================
 * Help for user and Main
 * ===================================================================== */

/* Help for the user */
INT32 Usage() {
    std::cerr << std::endl
        << "Usage" << std::endl
        << std::endl
        << "    pin -t (...)/mem_tracer.so -- <testing_application> [app_args]" << std::endl
        << std::endl
        << "This tool produces a trace of memory read/write operations on a specific" << std::endl
        << "memory block given by malloc() (not calloc). It is capable of tracing access" << std::endl
        << "to the block in single and multi-threaded applications." << std::endl
        << std::endl
        << "Each register contains 4 elements: thread, action, size, offset." << std::endl
        << "- thread  : An index (from zero) given to each thread of your process." << std::endl
        << "- Actions : R:read, W:write, Tc:thread_creation, Td:thread_destruction." << std::endl
        << "- Size    : The number of bytes being read or written. Its value (0) is" << std::endl
        << "            meaningless for Tc and Td." << std::endl
        << "- Offset  : The offset (in bytes) in the block at which the R/W happened." << std::endl
        << "            Its value (0) is meaningless for Tc and Td.";
    std::cerr << std::endl << KNOB_BASE::StringKnobSummary() << std::endl;
    return 1;
}

int main(int argc, char **argv) {
    // Initialize Pin lock, Pin itself, and Pin symbols
    PIN_InitLock(&pin_lock);
    if (PIN_Init(argc, argv))
        return Usage();
    PIN_InitSymbols();

    // Open the file to keep the log.
    // Write to a file since stdout and stderr may be used/closed by the application
    trace_file.open(trace_output_fname.Value().c_str());

    // Register Analysis routines to be called on:
    //
    // every malloc
    IMG_AddInstrumentFunction(image_load, 0);
    // every memory read/write operation
    INS_AddInstrumentFunction(rw_instructions, 0);
    // thread creation and destruction
    PIN_AddThreadStartFunction(thread_start, 0);
    PIN_AddThreadFiniFunction(thread_end, 0);
    // application termination (when the patient program ends)
    PIN_AddFiniFunction(Fini, 0);

    // Starts the patient program. It should never return.
    PIN_StartProgram();

    std::cout << "ERROR: PIN_StartProgram() shoud have not returned." << std::endl;
    return 1;
}
