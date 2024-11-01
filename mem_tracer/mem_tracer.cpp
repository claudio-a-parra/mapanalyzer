/* mem_tracer.cpp

Copyright (C) 2004-2021 Intel Corporation.
Copyright (C) 2023 Marco Bonelli.
Copyright (C) 2024 Claudio Parra.
SPDX-License-Identifier: MIT.

This pintool with the header mem_tracer.h provides a tool to select a block of
memory allocated with malloc() (not working for calloc), and trace all
accesses to such memory block. The tool records:
 - the timestamp of access.
 - the thread accessing the data.
 - the kind of access (R for read, W for write).
 - the size of the read/write (in bytes).
 - the offset from the beginning of the block (in bytes).
The trace is stored in a file called (by default) "mem_access_pattern.map"

Pin Manual:
https://software.intel.com/sites/landingpage/pintool/docs/98869/Pin/doc/html/index.html
*/

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
    = {.start=1, .end=0, .size=0, .being_traced=false};
/* Where to save the output.
Option for the pin command line tool. In this case: '-o output_filename'.
Its default value is 'mem_access_pattern.map' */
KNOB<std::string> map_filename(KNOB_MODE_WRITEONCE, "pintool", "o",
                   "mem_access_pattern.map", "Name of the output file.");

KNOB<std::string> collapse_time_jumps(KNOB_MODE_WRITEONCE, "pintool", "c",
                    "yes", "Allows collapsing those segments of time that have "
                    "no events from any thread. Otherwise simulate continious "
                    "execution. Values: yes (default), no.");


/* Where to store the logs of each thread.
Statically allocate MAX_THREADS Event traces (one for each possible thread in
the application). Each thread can register up to MAX_THR_EVENTS in their trace.

The idea is to avoid dynamic allocation. Why? because we are measuring real
time events and if we go down to the OS to request memory at runtime, well...
we fuck up all the measurments. */
const UINT16 MAX_THREADS = 32;
const UINT32 MAX_THR_EVENTS = 900000000; // 900,000,000 * 192 bytes =
std::stringstream metadata;
std::stringstream data;
std::stringstream error;
std::stringstream warning;
enum event_t{OTHER=0, Tc, Td, R, W};
enum write_only{ONLY_ERROR=0, WRITE_ALL};
const char* events_n[] = {"?","Tc","Td","R","W"};
typedef struct {        // 192 bytes
    UINT32 time;        // time in nanoseconds
    UINT32 coarse_time; // relative order time (computed at the end.
    UINT16 thrid;       // thread identifier
    UINT16 event;       // type of event (R, W,...)
    UINT32 size;        // size of the access
    UINT64 offset;      // offset from beginning of allocated block
} Event;
typedef struct {
    Event *list;        // pointer to the beginning of the trace
    UINT32 size;        // current number of elements in the trace
    INT32 min_time_gap; // the minimum time gap between consecutive accesses
    UINT64 overflow;    // counter for when we run out of memory.
    UINT64 pad[5];      // to avoid false sharing among cores
} ThreadTrace;
typedef struct {
    Event **list;       // pointer to the lists in each thread
    UINT64 list_len;    // number of lists (number of threads)
    UINT32 slice_size;  // min ThreadTrace.min_time_gap across all threads
} MergedTrace;

UINT64 basetime; // to subtract from every timestamp;
ThreadTrace thr_traces[MAX_THREADS];
MergedTrace merged_trace={.list=NULL,
                          .list_len=0,
                          .slice_size=INT32_MAX};


/* ======== Utility functions ======== */
/* core function that logs a thread event in the thread's queue */
void log_event(const THREADID thrid, const event_t event,
                const UINT32 size, const ADDRINT offset){
    if(thrid > MAX_THREADS){
        warning << "WARNING: Application tried to create more than "
                << MAX_THREADS
                << " threads. To do that, please change the MAX_THREADS"
                << " constant in the mem_trace pintool.";
        return;
    }
    // get new log index (tail of the queue)
    UINT32 new_log_idx = thr_traces[thrid].size;
    // just count if overflow
    if(new_log_idx >= MAX_THR_EVENTS){
        thr_traces[thrid].overflow +=1;
        return;
    }
    // get timestamp
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    UINT32 timestamp = (UINT32)((1000000000 * ts.tv_sec + ts.tv_nsec) - basetime);
    // write access log
    thr_traces[thrid].list[new_log_idx] =
        (Event){timestamp,0,(UINT16)thrid,event,size,offset};
    thr_traces[thrid].size += 1;
}


/**
   Write the output file with the contents of the error, warning, metadata, and
   data streams. This function is called before exiting. If "writing" is
   ONLY_ERROR, then most likely the function was called from an error point,
   and the idea is to just write the error and exit.
 **/
VOID write_file(enum write_only writing){
    std::ofstream out_file;
    out_file.open(map_filename.Value().c_str());
    // write error section
    if(error.tellp() != 0)
        out_file << "# ERROR" << std::endl
                 << error.rdbuf() << std::endl;
    if(writing == ONLY_ERROR)
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
        out_file << merged_trace.list[i]->coarse_time << ","
                 << merged_trace.list[i]->thrid << ","
                 << events_n[merged_trace.list[i]->event] << ","
                 << merged_trace.list[i]->size << ","
                 << merged_trace.list[i]->offset << std::endl;
    }

    out_file.close();
}


/**
   Three things are done in this function:
   - Individual thread traces are merged into a single trace sorted by each
     event's timestamp.
   - Real timestamps are made coarser based on the shortest gap between two
     sequential accesses done by some thread, this becomes the new unit of
     time.
   - Optionally (depending on the collapse_time_jumps KNOB) the merge procedure
     also collapses the gaps of coarse time with no activity in any thread,
     simulating an uninterrupted execution (this is the default behavior)
 **/
VOID merge_traces(void){
    // Two things are done in this loop:
    // 1. Count the total number of events (to be used in the merged list).
    // 2. Get the minimum timestamp-gap between two consecutive sequential
    //    accesses in any thread. This will become the unit of coarse time.
    merged_trace.slice_size = UINT32_MAX;
    for(UINT32 t=0; t<MAX_THREADS; t++){
        if(thr_traces[t].size < 1)
            // this thread didn't register any access.
            continue;
        merged_trace.list_len += thr_traces[t].size;
        if(thr_traces[t].size < 2){
            warning << "WARNING: Thread " << t << " registers only "
                    << "one event. Not useful to determine slice size."
                    << std::endl;
            continue;
        }
        // find the minimum timestamp-gap between two consecutive accesses in
        // this thread.
        INT64 this_gap;
        for(UINT32 j=0; j<thr_traces[t].size-2; j++){
            this_gap = \
              thr_traces[t].list[j+1].time - thr_traces[t].list[j].time;
            if(this_gap < merged_trace.slice_size)
                merged_trace.slice_size = this_gap;
        }
    }

    // Allocate space for merged list. This list just points to the events
    // in each thread's log.
    if(! merged_trace.list_len){
        error << "ERROR: No thread registered any event. "
              << "merged_trace.list_len == 0." << std::endl;
        write_file(ONLY_ERROR);
        exit(1);
    }
    merged_trace.list = (Event**)malloc(merged_trace.list_len * sizeof(Event*));
    if(! merged_trace.list){
        error << "ERROR: Could not allocate memory for merged_trace.list[]"
              << std::endl;
        write_file(ONLY_ERROR);
        exit(2);
    }

    // Now merge events from thr_trace[] in merged_trace[] such that they are
    // globally sorted by their timestamp
    UINT64 this_timestamp, earliest_timestamp;
    UINT32 front[MAX_THREADS] = {0};
    INT64 earliest_thread;
    for(UINT64 e=0; e<merged_trace.list_len; e++){
        // find the thread such that its front event is the earliest.
        earliest_thread = -1;
        earliest_timestamp = UINT64_MAX;
        for(INT32 thr=0; thr<MAX_THREADS; thr++){
            // if the index to the front event in this thread trace is out of
            // boundaries, that means that this thread trace has no more events.
            if(front[thr] >= thr_traces[thr].size)
                continue;

            // if this thread's front event is the earliest among all threads
            // checked so far, then remember this thread and the timestamp.
            this_timestamp = thr_traces[thr].list[front[thr]].time;
            if(this_timestamp < earliest_timestamp){
                earliest_thread = thr;
                earliest_timestamp = this_timestamp;
            }
        }
        // Add the earliest event to the merged_trace[], and increment the
        // "front event" of that thread.
        if(earliest_thread == -1){
            error << "ERROR: Impossible timestamp == UINT64_MAX registered "
                  << "by thread " << earliest_thread << "."
                  << std::endl;
            write_file(ONLY_ERROR);
            exit(1);
        }
        merged_trace.list[e] = \
          &(thr_traces[earliest_thread].list[front[earliest_thread]]);
        front[earliest_thread] += 1;
    }

    // convert nanosecond (time) into coarse time based on the shortest time-gap
    basetime = merged_trace.list[0]->time;
    UINT32 slice_size = merged_trace.slice_size;
    for(UINT64 e=0; e<merged_trace.list_len; e++){
        merged_trace.list[e]->coarse_time = \
      (merged_trace.list[e]->time - basetime) / slice_size;
    }

    /* Optionally collapse segments of time without activity.
    If true, the idea of the trace would be to show the temporal relationship
    among events, not their absolute location during the execution. This
    simulates a "continuous execution". */
    if(collapse_time_jumps.Value() == "yes"){
        UINT32 shift = 0;
    Event *ev;
    UINT32 last_coarse_time=0;
    for(UINT64 e=0; e<merged_trace.list_len; e++){
        ev = merged_trace.list[e];
        if(ev->coarse_time - shift > last_coarse_time + 1)
            shift = ev->coarse_time - last_coarse_time -1;
        ev->coarse_time = ev->coarse_time - shift;
        last_coarse_time = ev->coarse_time;
        }
    }
    return;
}





/* ======== Analysis Routines ======== */
/* This routine is called every time a thread is created */
// VOID thread_start(THREADID threadid, CONTEXT* ctxt, INT32 flags, VOID* v){
//     log_event(threadid, Tc, 0, 0);
// }
/* This routine is called every time a thread is destroyed. */
// VOID thread_end(THREADID threadid, const CONTEXT* ctxt, INT32 code, VOID* v){
//     log_event(threadid, Td, 0, 0);
// }

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
    }
    tracked_block.start = retval;
    tracked_block.end = retval + tracked_block.size - 1;

    // if patient called malloc() requesting a block of size 0.
    if (!tracked_block.size) {
        error << "ERROR: Was malloc() called with argument 0? "
                  << "Block of size zero. Nothing to trace." << std::endl;
        PIN_ExitApplication(3);
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
                  << "a block of memory. Did you call mt_select_next_block() "
                  << "before the malloc() that reserves the block that you "
                  << "want to trace?" << std::endl;
        PIN_ExitApplication(1);
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
    tracked_block = {.start=1, .end=0, .size=0, .being_traced=false};
}

/* Executed *before* a free() call: if the freed block is being traced,
then stop the trace. */
VOID free_before(ADDRINT addr, THREADID threadid) {
    // if free was called upon the tracked memory block, then stop tracing.
    PIN_GetLock(&pin_lock, threadid + 1);
    if (tracked_block.being_traced == true && addr == tracked_block.start){
        action_stop_tracing();
        error << "Trace stopped prematurely: thread " << threadid
              <<" called free("
              << std::hex << std::showbase
              << addr
              << std::noshowbase << std::dec
              << ")." << std::endl;
    }
    PIN_ReleaseLock(&pin_lock);
}

/* Executed *before* any read operation: registers address and read size */
VOID trace_read_before(ADDRINT ip, ADDRINT addr, UINT32 size,
                       THREADID threadid) {
    // if the addr is out of the monitored address range, or we are not
    //tracing, or reading nothing
    ADDRINT offset = addr - tracked_block.start;
    if (offset >= tracked_block.size || offset < 0 ||
        !tracked_block.being_traced || !size)
        return;
    log_event(threadid, R, size, offset);
}

/* Executed *before* any write operation: registers address and write size */
VOID trace_write_before(ADDRINT ip, ADDRINT addr, UINT32 size,
                        THREADID threadid) {
    // if the addr is out of the monitored address range, or we are not
    //tracing, or writing nothing
    ADDRINT offset = addr - tracked_block.start;
    if (offset >= tracked_block.size || offset < 0 ||
        !tracked_block.being_traced || !size)
        return;
    log_event(threadid, W, size, offset);
}


/* ======== Instrumentation Routines ======== */
/* Alter the binary image, so that certain routines can be surrounded by the
   code here defined. */
VOID image_load(IMG img, VOID* v) {
    // The concept of "Instrumenting a function" is like "tampering" the
    // execution of a given function. So another function can run before or
    // after it.

    // Instrument the flag-functions avalible to the user.
    // - mt_select_next_block()
    // - mt_start_tracing()
    // - mt_stop_tracing()

    // Just before the analyzed code calls mt_select_next_block(), the pintool
    // will call action_select_next_block().
    RTN select_routine = RTN_FindByName(img, "mt_select_next_block");
    if (RTN_Valid(select_routine)) {
        RTN_Open(select_routine);
        RTN_InsertCall(select_routine,
                       IPOINT_BEFORE,
                       (AFUNPTR)action_select_next_block,
                       IARG_END);
        RTN_Close(select_routine);
    }
    // The same idea applies for mt_start_tracing() and mt_stop_tracing().
    RTN start_routine = RTN_FindByName(img, "mt_start_tracing");
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
    RTN stop_routine = RTN_FindByName(img, "mt_stop_tracing");
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
    // analized code, but given the definitions of "malloc_before" and
    // "malloc_after", stuff only happens when the analyzed code has
    // previously called "mt_select_next_block".
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

    // In case the analyzed code has not called "mt_stop_tracing", anyway
    // stop the tracing if it calls "free".
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

/* Alter instructions so that upon detection of certain kind of instructions,
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
VOID Fini(INT32 code, VOID* v) {
    // if finishing application not nicely, then report error and exit.
    if(code != 0){
        error << "ERROR: Pintool terminated the application with code "
              << code << "." << std::endl;
        write_file(ONLY_ERROR);
        exit(3);
    }

    // count threads and detect whether there were events overflows in them
    UINT32 thread_count=0;
    for(UINT32 i=0; i<MAX_THREADS; i++){
        if(thr_traces[i].size < 1)
            continue;
        thread_count += 1;
        if(thr_traces[i].overflow > 0){
            warning << "Thread " << i << " could not register "
                    << thr_traces[i].overflow << " events!" << std::endl;
        }
    }

    // merge the thread traces
    merge_traces();

    // complete metadata info
    Event *last_event = merged_trace.list[merged_trace.list_len-1];
    metadata << "slice-size   : " << merged_trace.slice_size << std::endl
             << "thread-count : " << thread_count << std::endl
             << "event-count  : " << merged_trace.list_len << std::endl
             << "max-time     : " << last_event->coarse_time << std::endl;

    // and now, wrap it all and put a bow on it :D
    write_file(WRITE_ALL);
}


/* ======== Help for user and Main ======== time,thread,event,size,offset */
/* Help for the user */
INT32 Usage() {
    std::cerr
        << std::endl
        << "Usage" << std::endl
        << std::endl
        << "    pin -t (...)/mem_tracer.so [-c yes|no] -- "
      "<testing_application> [test_app_args]"
        << std::endl
        << std::endl
        << "This tool produces a trace of memory read/write events on a "
      "specific memory block given by malloc() (not calloc). It is capable of "
      "tracing accesses to the block in single and multi-threaded applications."
        << std::endl
        << std::endl
        << "Each event contains 4 elements: time, thread, event, size, offset."
        << std::endl
        << " - thread : An index (from zero) given to each thread of your "
      "process."
        << std::endl
        << " - event  : R:read, W:write."
        << std::endl
        << " - size   : The number of bytes being read or written."
        << std::endl
        << " - offset : The offset (in bytes) within the block at which the "
      "access happened."
        << std::endl
        << std::endl
        << KNOB_BASE::StringKnobSummary()
        << std::endl;
    return 1;
}

int main(int argc, char **argv) {
    // Initialize Pin lock, Pin itself, and Pin symbols
    PIN_InitLock(&pin_lock);
    if (PIN_Init(argc, argv))
        return Usage();
    PIN_InitSymbols();

    // allocate space for the logs
    // Maybe implement a dynamic memory allocation system. to avoid running
    // out of memory.
    // Use PIN_StopApplicationThreads(), so threads stop while allocating
    // memory, avoiding strange timings due to the mallocs.
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
    // - every malloc and free
    IMG_AddInstrumentFunction(image_load, 0);
    // - every memory read/write operation
    INS_AddInstrumentFunction(rw_instructions, 0);
    // - application termination (when the analyzed program ends)
    PIN_AddFiniFunction(Fini, 0);

    // get an early basetime to subtract every to timestamp. During merging
    // this is updated so that the first event always has timestamp = 0.
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    basetime = 1000000000 * ts.tv_sec + ts.tv_nsec;

    // Starts the analyzed program. This function never returns.
    PIN_StartProgram();

    error << "ERROR: PIN_StartProgram() shoud have not returned." << std::endl;
    Fini(1, NULL);
    return 1;
}
