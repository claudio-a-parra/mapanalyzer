/* memtrace.cpp
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
struct tracked_malloc_block {
    ADDRINT start;
    ADDRINT end;
    ADDRINT size;
    bool tracing;
};
// whether to select the next allocated block (through malloc) for tracing.
// It has three values:
//   0: do not pay attention to the next malloc.
//   1: pay attention to the next malloc. Function malloc_before has not
//      ran yet. Only accepted value for malloc_before to run.
//   2: malloc found, and malloc_before has ran. Only accepted value for
//      malloc_after to run.
// So the cycle is: 0 -> select -> 1 -> malloc_before -> 2 -> malloc_after -> 0
char select_next_block = 0;
std::ofstream trace_file;
struct tracked_malloc_block tracked_block
    = {.start=0, .end=0, .size=0, .tracing=false};
KNOB<std::string> trace_output_fname(
    KNOB_MODE_WRITEONCE, "pintool", "o",
    "mem_trace_log.out", "specify trace file name");


/* Sets flag such that the next time the pintool calls {m,c}alloc_before() and
 * {m,c}alloc_after(), the addres and size given to/by that patient:malloc()
 * is saved. */
VOID action_select_next_block(){
    select_next_block = 1;
}

/* Executed *before* a malloc() call: save block size. */
VOID malloc_before(ADDRINT size) {
    // if action_select_next_block has not ran yet, abort.
    if (select_next_block != 1)
        return;
    select_next_block = 2;
    tracked_block.size = size;
}
/* Executed *after* a malloc() call: save block's address and end address */
VOID malloc_after(ADDRINT retval) {
    // if malloc_before has not ran yet, abort.
    if (select_next_block != 2)
        return;

    // if malloc failed to allocate a block of memory.
    if (retval == 0) {
        trace_file << "ERROR: malloc() failed and returned 0!" << std::endl;
        return;
    }
    tracked_block.start = retval;
    tracked_block.end = retval + tracked_block.size;

    // if patient called malloc() requesting a block of size 0.
    if (!tracked_block.size) {
        trace_file << "ERROR: Was malloc() called with argument 0? "
                   << "Block of size zero. Nothing to trace." << std::endl;
        return;
    }

    // log to file
    trace_file << std::hex << std::showbase
               << "START_ADDR   : " << tracked_block.start << std::endl
               << "END_ADDR     : " << tracked_block.end   << std::endl
               << std::noshowbase << std::dec
               << "SIZE (bytes) : " << tracked_block.size  << std::endl
               << std::endl;
    trace_file << "core,action,size,offset" << std::endl;

    // reset flag so following mallocs are not tracked.
    select_next_block = 0;
}




/* If a block is not being traced, then start tracing it. */
VOID action_start_tracing(){
    // if we are ALREADY tracing, then there is nothing to do.
    if (tracked_block.tracing)
        return;

    // if there is no block to trace, or its size is zero
    if (!tracked_block.start || !tracked_block.size) {
        trace_file << tracked_block.start << " , " << tracked_block.size << std::endl;

        trace_file << "ERROR: Cannot start tracing without having allocated "
                   << "a block of memory. Did you call instr_select_next_block() "
                   << "before the malloc() that reserves the block that you want "
                   << "to trace?" << std::endl;
        return;
    }

    // log tracing start
    // trace_file << "TRACING START : ["
    //            << std::hex << std::showbase
    //            << tracked_block.start << "-" << tracked_block.end
    //            << std::noshowbase << std::dec
    //            << "] (" << tracked_block.size << " bytes)" << std::endl;

    // set flag so that R/W instructions are recorded in the trace file.
    tracked_block.tracing = true;
}
/* If a block is being traced, then stop tracing it. */
VOID action_stop_tracing(){
    // if we are not tracing, then there is nothing to do.
    if (!tracked_block.tracing)
        return;

    // log tracing stop
    // trace_file << "TRACING STOP  : ["
    //            << std::hex << std::showbase
    //            << tracked_block.start << "-" << tracked_block.end
    //            << std::noshowbase << std::dec
    //            << "] (" << tracked_block.size << " bytes)" << std::endl;

    // clears tracked memory block, so future R/W instructions don't
    // record anything on the trace file.
    tracked_block = {.start=0, .end=0, .size=0, .tracing=false};
}
/* Executed *before* a free() call: if the freed block is being traced,
 * then stop the trace. */
VOID free_before(ADDRINT addr) {
    // if free was called upon the tracked memory block, then stop tracing.
    if (addr == tracked_block.start){
        action_stop_tracing();
        trace_file << "TRACE STOPPED DUE TO SELECTED BLOCK HAS BEEN FREED. free("
                   << std::hex << std::showbase
                   << addr
                   << std::noshowbase << std::dec
                   << ")" << std::endl;
    }
}


/* Executed *before* any read operation: registers address and read size */
VOID trace_read_before(ADDRINT ip, ADDRINT addr, UINT32 size) {
    // if we are tracing nothing, or reading nothing, or reading before or after
    // the monitored block; then do nothing.
    ADDRINT offset = addr - tracked_block.start;
    if (!tracked_block.tracing || !tracked_block.size || !size ||
        offset < 0 || offset >= tracked_block.size)
        return;

    trace_file
        << "99,"
        << "R,"
        << size << ","
        << offset << std::endl;
}
/* Executed *before* any write operation: registers address and write size */
VOID trace_write_before(ADDRINT ip, ADDRINT addr, UINT32 size) {

    // if we are tracing nothing, or writing nothing, or writing before or after
    // the monitored block; then do nothing.
    ADDRINT offset = addr - tracked_block.start;
    if (!tracked_block.tracing || !tracked_block.size || !size ||
        offset < 0 || offset >= tracked_block.size)
        return;

    trace_file
        << "99,"
        << "W,"
        << size << ","
        << offset << std::endl;
}




/* "Modify" the binary image, so that new routines can be injected before and
 * after certain routines originally in the image. */
VOID Image(IMG img, VOID* v) {
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
    RTN select_rtn = RTN_FindByName(img, "instr_select_next_block");
    if (RTN_Valid(select_rtn)) {
        RTN_Open(select_rtn);
        RTN_InsertCall(select_rtn,
                       IPOINT_BEFORE,
                       (AFUNPTR)action_select_next_block,
                       IARG_END);
        RTN_Close(select_rtn);
    }
    // The same idea applies for patient's functions instr_start_tracing()
    // and instr_stop_tracing().
    RTN start_rtn = RTN_FindByName(img, "instr_start_tracing");
    if (RTN_Valid(start_rtn)) {
        RTN_Open(start_rtn);
        RTN_InsertCall(start_rtn,
                       IPOINT_BEFORE,
                       (AFUNPTR)action_start_tracing,
                       IARG_END);
        RTN_Close(start_rtn);
    }
    RTN stop_rtn = RTN_FindByName(img, "instr_stop_tracing");
    if (RTN_Valid(stop_rtn)) {
        RTN_Open(stop_rtn);
        RTN_InsertCall(stop_rtn,
                       IPOINT_BEFORE,
                       (AFUNPTR)action_stop_tracing,
                       IARG_END);
        RTN_Close(stop_rtn);
    }

    // Instrument malloc() to save the address and size of the block.
    // Note that this instrumentation happens for any malloc in the
    // patient code, but given the definitions of "malloc_before" and
    // "malloc_after", stuff only happens when the patient has
    // previously called "instr_select_next_block".
    RTN malloc_rtn = RTN_FindByName(img, "malloc");
    if (RTN_Valid(malloc_rtn)) {
        RTN_Open(malloc_rtn);
        RTN_InsertCall(malloc_rtn,
                       IPOINT_BEFORE,
                       (AFUNPTR)malloc_before,
                       // pass the value of the 0th argument of
                       // malloc() to malloc_before()
                       IARG_FUNCARG_ENTRYPOINT_VALUE, 0,
                       IARG_END);
        RTN_InsertCall(malloc_rtn,
                       IPOINT_AFTER,
                       (AFUNPTR)malloc_after,
                       // pass the return value of malloc() to
                       // malloc_after()
                       IARG_FUNCRET_EXITPOINT_VALUE,
                       IARG_END);
        RTN_Close(malloc_rtn);
    }

    // In case the patient has not called "instr_stop_tracing", anyway
    // stop the tracing if patient code calls "free".
    RTN free_rtn = RTN_FindByName(img, "free");
    if (RTN_Valid(free_rtn)) {
        RTN_Open(free_rtn);
        RTN_InsertCall(free_rtn,
                       IPOINT_BEFORE,
                       (AFUNPTR)free_before,
                       // pass the zero-th argument's value of free() to
                       // free_before()
                       IARG_FUNCARG_ENTRYPOINT_VALUE, 0,
                       IARG_END);
        RTN_Close(free_rtn);
    }
}

/* "Modify" instructions so that upon detection of certain kind of instructions,
 * extra code could run before or after them. Here, we are tampering all memory
 * read and write instructions */
VOID Instruction(INS ins, VOID* v) {
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
                IARG_END);
        }
    }
}

/* What to do at the end of the execution. */
VOID Fini(INT32 code, VOID* v) {
    trace_file.close();
}

/* Help for the user */
INT32 Usage() {
    std::cerr << "This tool produces a trace of memory read/write operations"
        << " on a specific memory block given by malloc() (not calloc)" << std::endl;
    std::cerr << std::endl << KNOB_BASE::StringKnobSummary() << std::endl;
    return 1;
}




int main(int argc, char **argv) {
    PIN_InitSymbols();

    if (PIN_Init(argc, argv))
        return Usage();

    // Write to a file since stdout and stderr may be closed by the application
    trace_file.open(trace_output_fname.Value().c_str());

    IMG_AddInstrumentFunction(Image, 0);
    INS_AddInstrumentFunction(Instruction, 0);
    PIN_AddFiniFunction(Fini, 0);

    PIN_StartProgram(); // never returns

    std::cout << "ERROR: PIN_StartProgram() shoud have not returned." << std::endl;
    return 1;
}
