/* mem_tracer.cpp

Copyright (C) 2004-2021 Intel Corporation.
Copyright (C) 2023 Marco Bonelli.
Copyright (C) 2023 Claudio Parra.
SPDX-License-Identifier: MIT.

This pintool with the header instr.h provides a tool to select a block of
memory allocated with malloc() (not working for calloc), and trace all
accesses to such memory block. The tool records:
 - the kind of access (R for read, W for write).
 - the size of the read/write (in bytes).
 - the offset from the beginning of the block (in bytes).
The trace is stored in a file called (by default) "mem_trace_log.out" */

#include "pin.H"
#include <ctime> // C library 'time.h'
#include <iostream>
#include <fstream>
#include <iomanip> // to set doubles precision
                   //
/* tracked memory block */
struct tracked_malloc_block {
    ADDRINT start;     // First address of the block
    ADDRINT end;       // Last address of the block
    ADDRINT size;      // The size of the block in bytes
    bool being_traced; // Whether this block is currently being traced.
                       // This value is false until action_start_tracing()
                       // is called.
};
/* To ensure "select block", "malloc before", and "malloc after" are
 called in exactly that order. */
enum SEL_BLOCK{NO_SELECTION, PRE_BEF_MALLOC, POST_BEF_MALLOC};
/* Whether to select the next allocated block (through malloc) for tracing.
It has three values:
  0: do not pay attention to the next malloc.
  1: pay attention to the next malloc. Function malloc_before has not
     ran yet. Only accepted value for malloc_before to run.
  2: malloc found, and malloc_before has ran. Only accepted value for
     malloc_after to run.
So the cycle is: 0 -> select -> 1 -> malloc_before -> 2 -> malloc_after -> 0
*/
SEL_BLOCK select_next_block = NO_SELECTION;
/* This lock serializes the access to the output file (trace_file) */
PIN_LOCK pin_lock;
/* tracked memory block */
struct tracked_malloc_block tracked_block
    = {.start=0, .end=0, .size=0, .being_traced=false};
/* Where to save the output.
   Option for the pin command line tool. In this case: '-o output_filename'.
   Its default value is 'mem_trace_log.out' */
KNOB<std::string> trace_output_fname(KNOB_MODE_WRITEONCE, "pintool", "o",
                                     "mem_trace_log.out","Output filename");


/* Where to store the logs of each thread.
 Statically allocate MAX_THREADS Event Logs (one for each possible thread in
 the application). Each thread can register up to MAX_THR_EVENTS in their log.

 This is done in this manner to avoid dynamic allocation. Why? because we are
 measuring real time events and if we go down to the OS to request memory
 at runtime, well... we fuck up all the measurments. */
const UINT16 MAX_THREADS = 32;
const UINT32 MAX_THR_EVENTS = 64000;
std::stringstream metadata;
std::stringstream data;
std::stringstream error;
std::stringstream warning;
enum event_t{OTHER, Tc, Td, R, W};
const char* events_n[] = {"?","Tc","Td","R","W"};
typedef struct {
    UINT32 time;
    UINT32 qtime;
    UINT16 thrid;
    UINT16 event;
    UINT32 size;
    UINT64 offset;
} Event;
typedef struct {
    Event *list;
    UINT32 size;
    INT32 min_time_gap;
    UINT64 overflow;
    UINT64 pad[5]; // to avoid false sharing among cores
} ThreadTrace;
typedef struct {
    Event **list;
    UINT64 list_len;
    UINT32 slice_size;
} MergedTrace;

UINT64 basetime; // to subtract from every timestamp;
ThreadTrace thr_traces[MAX_THREADS];
MergedTrace merged_trace={.list=NULL,
                          .list_len=0,
                          .slice_size=INT32_MAX};
/* ======== Utilitarian functions ======== */
/* log a thread event in its own queue */
void log_event(const THREADID thrid, const event_t event,
                const UINT32 size, const ADDRINT offset){
    if(thrid > MAX_THREADS){
        warning << "WARNING: Application tried to create more than "
                << MAX_THREADS
                << " threads. To do that, please change the MAX_THREADS"
                << " constant in the mem_trace pintool.";
        return;
    }
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    UINT32 timestamp = (UINT32)((1000000000 * ts.tv_sec + ts.tv_nsec) - basetime);
    UINT32 idx = thr_traces[thrid].size;
    if(idx < MAX_THR_EVENTS){
        thr_traces[thrid].list[idx] =
            (Event){timestamp,0,(UINT16)thrid,event,size,offset};
        thr_traces[thrid].size += 1;
        return;
    }
    thr_traces[thrid].overflow +=1;
}




VOID write_file(UINT32 exit_now);
VOID Fini(INT32 code, VOID* v);


VOID merge_traces(void){

    // Two things are done here:
    // 1. Get the minimum time-gap between two sequential accesses in any same
    // thread.
    // 2. Count the total number of events (to be used in the merged list).
    merged_trace.slice_size = UINT32_MAX;
    for(UINT32 t=0; t<MAX_THREADS; t++){
        // std::cout << "t:" << t << std::endl;
        if(thr_traces[t].size < 1)
            continue;
        //thr_traces[t].min_time_gap = INT32_MAX;
        merged_trace.list_len += thr_traces[t].size;
        if(thr_traces[t].size < 2){
            warning << "WARNING: Thread " << t << " registers only "
                    << "one event. Not useful to determine slice size."
                    << std::endl;
            continue;
        }
        for(UINT32 j=0; j<thr_traces[t].size-2; j++){
            INT64 this_gap = thr_traces[t].list[j+1].time \
                - thr_traces[t].list[j].time;
            // std::cout << "t[" << j+1 << "] - t[" << j << "] "
            //           << "gap:" << this_gap << std::endl;
            if(this_gap < merged_trace.slice_size)
                merged_trace.slice_size = this_gap;
        }
    }


    // Allocate space for merged list. This list just points to the events
    // in each thread's log.
    if(! merged_trace.list_len){
        error << "ERROR: No thread registered any event. "
              << "merged_trace.list_len == 0." << std::endl;
        write_file(1);
        exit(1);
    }
    merged_trace.list = (Event**)malloc(merged_trace.list_len * sizeof(Event*));
    if(! merged_trace.list){
        error << "ERROR: Could not allocate memory for merged_trace.list[]"
              << std::endl;
        write_file(1);
        exit(1);
    }


    // Now merge events such that they are globally sorted by their timestamp
    UINT64 earliest_timestamp;
    UINT32 front[MAX_THREADS] = {0};
    INT64 t_star;
    for(UINT64 e=0; e<merged_trace.list_len; e++){
        // find the thread t_star such that its front event is the earliest.
        t_star = -1;
        earliest_timestamp = UINT64_MAX;
        for(INT32 t=MAX_THREADS-1; t>=0; t--){
            // if the index to the front event in this thread trace is out of
            // boundaries, that means that this thread trace has no more events.
            if(! (front[t] < thr_traces[t].size))
                continue;

            // if this thread's front event is the earliest among all threads
            // checked so far, then remember this thread and the timestamp.
            if(thr_traces[t].list[front[t]].time <= earliest_timestamp){
                t_star = t;
                earliest_timestamp = thr_traces[t].list[front[t]].time;
            }
        }

        // Add the event found to be the earliest, to the merged_log list, and
        // move the "front event" of that thread to the next position.
        merged_trace.list[e] = &(thr_traces[t_star].list[front[t_star]]);
        front[t_star] += 1;
    }


    // convert nanosecond (time) timestamps to timeslices (qtime)
    basetime = merged_trace.list[0]->time;
    for(UINT64 e=0; e<merged_trace.list_len; e++){
        merged_trace.list[e]->qtime = (merged_trace.list[e]->time - basetime)
            /(merged_trace.slice_size);
    }


    // Remove long qtime jumps.
    // The idea of the trace is to show the "before-after" relationship,
    // so if we have a long jump in qtimes where no thread does anything,
    // let's better cut it off to simulate a "contiguous" execution.
    // For example:
    //   Let's say the qtime of the last two events from thread
    //   0 and thread 1 is qtime=43. And the next three events
    //   from thread 1, 2, and 3; is 99.
    //   There is no point to leave 99-43=56 qtimes empty, so we
    //   shift all the subsequent events (starting from those
    //   three with qtime=99) by -55, so they keep counting from
    //   44 and ahead.
    UINT32 shift = 0;
    Event *ev;
    UINT32 last_qtime=0;
    for(UINT64 e=0; e<merged_trace.list_len; e++){
        ev = merged_trace.list[e];
        if(ev->qtime - shift > last_qtime + 1)
            shift = ev->qtime - last_qtime -1;
        ev->qtime = ev->qtime - shift;
        last_qtime = ev->qtime;
    }
    return;
}





/* ======== Analysis Routines ======== */
 /* This routine is called every time a thread is created */
VOID thread_start(THREADID threadid, CONTEXT* ctxt, INT32 flags, VOID* v){
    log_event(threadid, Tc, 0, 0);
}
/* This routine is called every time a thread is destroyed. */
VOID thread_end(THREADID threadid, const CONTEXT* ctxt, INT32 code, VOID* v){
    log_event(threadid, Td, 0, 0);
}
/* Sets flag such that the next time the pintool calls malloc_before(),
the size given to malloc is recorded */
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
end addresses */
VOID malloc_after(ADDRINT retval, THREADID threadid) {
    PIN_GetLock(&pin_lock, threadid + 1);
    // if malloc_before has not ran yet, abort.
    if (select_next_block != POST_BEF_MALLOC){
        PIN_ReleaseLock(&pin_lock);
        return;
    }

    // if malloc failed to allocate a block of memory.
    if (retval == 0) {
        error << "ERROR: malloc() failed and returned 0!" << std::endl;
        PIN_ExitApplication(2);
        //PIN_ReleaseLock(&pin_lock);
        //return;
    }
    tracked_block.start = retval;
    tracked_block.end = retval + tracked_block.size;

    // if patient called malloc() requesting a block of size 0.
    if (!tracked_block.size) {
        error << "ERROR: Was malloc() called with argument 0? "
                  << "Block of size zero. Nothing to trace." << std::endl;
        PIN_ExitApplication(3);
        //PIN_ReleaseLock(&pin_lock);
        //return;
    }

    // save metadata
    metadata << std::hex << std::showbase
             << "start-addr   : " << tracked_block.start << std::endl
             << "end-addr     : " << tracked_block.end   << std::endl
             << std::noshowbase << std::dec
             << "block-size   : " << tracked_block.size  << std::endl
             << "owner-thread : " << threadid     << std::endl;

    data << "time,thread,event,size,offset" << std::endl;

    // reset flag so following mallocs are not tracked.
    select_next_block = NO_SELECTION;
    PIN_ReleaseLock(&pin_lock);
}
/* NOTE: record the barriers so I can "re-sync" the x-possition of all threads
 accesses from the perspective of the one calling the sync. This will avoid
 the apparent trans-barrier data overlap. it would be neat to draw it... */


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
        error << "Block start: " << tracked_block.start << std::endl
                  << "Block size : " << tracked_block.size << std::endl;
        error << "ERROR: Cannot start tracing without having allocated "
                  << "a block of memory. Did you call instr_select_next_block() "
                  << "before the malloc() that reserves the block that you want "
                  << "to trace?" << std::endl;
        PIN_ExitApplication(1);
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
then stop the trace. */
VOID free_before(ADDRINT addr, THREADID threadid) {
    // if free was called upon the tracked memory block, then stop tracing.
    PIN_GetLock(&pin_lock, threadid + 1);
    if (tracked_block.being_traced == true && addr == tracked_block.start){
        action_stop_tracing();
        error << "Trace stopped. free("
                  << std::hex << std::showbase
                  << addr
                  << std::noshowbase << std::dec
                  << ") called by thread " << threadid
                  << "." << std::endl;
        PIN_ExitApplication(0);
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
    log_event(threadid, R, size, offset);
}
/* Executed *before* any write operation: registers address and write size */
VOID trace_write_before(ADDRINT ip, ADDRINT addr, UINT32 size, THREADID threadid) {
    // if we are tracing nothing, or writing nothing, or writing before or after
    // the monitored block; then do nothing.
    ADDRINT offset = addr - tracked_block.start;
    if (!tracked_block.being_traced || !tracked_block.size || !size ||
        offset < 0 || offset >= tracked_block.size)
        return;
    log_event(threadid, W, size, offset);
}


/* ======== Instrumentation Routines ======== */
/* "Modify" the binary image, so that new routines can be injected before and
after certain routines originally in the image. */
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
extra code could run before or after them. Here, we are tampering all memory
read and write instructions */
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

VOID write_file(UINT32 exit_now){
    std::ofstream out_file;
    out_file.open(trace_output_fname.Value().c_str());
    // write error section
    if(error.tellp() != 0)
        out_file << "# ERROR" << std::endl
                 << error.rdbuf() << std::endl;
    if(exit_now)
        return;

    // write warning section
    if(warning.tellp() != 0)
        out_file << "# WARNING" << std::endl
                 << warning.rdbuf() << std::endl;

    // write metadata section
    if(metadata.tellp() != 0)
        out_file << "# METADATA" << std::endl
                 << metadata.rdbuf() << std::endl;

    // write data section
    out_file << "# DATA" << std::endl
             << data.rdbuf();
    for(UINT64 i=0; i<merged_trace.list_len; i++){
        out_file << merged_trace.list[i]->qtime << ","
                 << merged_trace.list[i]->thrid << ","
                 << events_n[merged_trace.list[i]->event] << ","
                 << merged_trace.list[i]->size << ","
                 << merged_trace.list[i]->offset << std::endl;
    }

    out_file.close();
}

VOID Fini(INT32 code, VOID* v) {
    // if finishing application not nicely, then report error and exit.
    if(code != 0){
        error << "ERROR: Pintool terminated the application with code "
              << code << "." << std::endl;
        write_file(1);
        return;
    }

    // count total threads and detect events overflow in threads
    UINT32 thread_count=0;
    for(UINT32 i=0; i<MAX_THREADS; i++){
        if(thr_traces[i].size < 1)
            continue;
        thread_count += 1;
        if(thr_traces[i].overflow > 0){
            warning << "Thread " << i << " could not log "
                    << thr_traces[i].overflow << " events!" << std::endl;
        }
    }

    // merge the thread traces
    merge_traces();

    // complete metadata info
    metadata << "slice-size   : " << merged_trace.slice_size << std::endl;
    metadata << "thread-count : " << thread_count << std::endl;
    metadata << "event-count  : " << merged_trace.list_len << std::endl;
    metadata << "max-qtime    : " << merged_trace.list[merged_trace.list_len-1]->qtime << std::endl;

    // and now write the file
    write_file(0);
}


/* ======== Help for user and Main ======== */

/* Help for the user */
INT32 Usage() {
    std::cerr
        << std::endl
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

    //
    // allocate space for the logs
    Event *e_list;
    for(UINT32 i=0; i<MAX_THREADS; i++){
        e_list = (Event*) malloc(MAX_THR_EVENTS * sizeof(Event));
        if(!e_list){
            error << "Could not allocate memory for "
                      << MAX_THREADS <<" thead logs." << std::endl;
            Fini(1, NULL);
            exit(1);
        }
        thr_traces[i].list = e_list;
        thr_traces[i].size = 0;
        thr_traces[i].overflow = 0;
    }


    // Register routines to instrument:
    // every malloc
    IMG_AddInstrumentFunction(image_load, 0);
    // every memory read/write operation
    INS_AddInstrumentFunction(rw_instructions, 0);
    // thread creation and destruction
    PIN_AddThreadStartFunction(thread_start, 0);
    PIN_AddThreadFiniFunction(thread_end, 0);
    // application termination (when the patient program ends)
    PIN_AddFiniFunction(Fini, 0);

    // get the basetime to subtract every to timestamp
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    basetime = 1000000000 * ts.tv_sec + ts.tv_nsec;

    // Starts the patient program. It should never return.
    PIN_StartProgram();

    std::cout << "ERROR: PIN_StartProgram() shoud have not returned." << std::endl;
    return 1;
}
