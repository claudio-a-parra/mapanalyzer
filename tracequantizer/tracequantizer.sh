#!/bin/env bash

# Alright, so if you are reading this shit, that means that you are deep into
# the weeds with memory tracing. Good, coz that means that at least my PhD was
# read by some other human (or machine?). If you are either of them, send me
# your greeting at parraca at uci dot edu. Btw, this crap is licenced to you
# as Creative Commons, so use it, but tell the world that I started this
# nonsense so they can blame me instead of you.
#
# So what is this about? This is a bash script that contains (at the bottom)
# some C code and AWK script. The idea was to pack everything together.
# Literally to 'keep my shit together'.
#
# The idea of this script is to find how quick a thread can request two
# consecutive memory accesses (under the pin tooling, of course, that stuff
# has overhead.) The point is to be able to realistically represent the total
# order of the events captured by the pintool mem_tracer.so, and identify
# events those events that "happened at the same time", even if they did not
# happen at the very same nanosecond.
#
# By the way, the mem_tracer.so tool is a tool that I developed on top of
# Intel Pin, you should have found its code somewhere alongside this script,
# otherwise, pray for my to still have a copy of it.
#
# Once this "minimum time" is found, we modify the log produced by mem_tracer.so
# so its timestamp is not nanoseconds, but just consecutive numbers depicting
# the total order of events. If two events happens with less than that
# "minimum-time" of difference, they are represented as happening at the same
# time (concurrently)
#
# That's it.


# obtain a piece of this very file as an independent file
embedded_file(){
    # The idea is that you can embed text files within this very script and
    # use those files later, for example:
    # ------------------------
    # your blah blah
    # in this script
    # #BEGIN_WHATEVER
    # the embedded script
    # goes here
    # #END_WHATEVER
    # ------------------------
    # Then by calling 'embedded_file WHATEVER' you get the text between the
    # #BEGIN_ and #END_ lines. Now, by calling it with process substitution,
    # like '<(embedded_file WHATEVER)', you get a handle to a file with that
    # content. This is called a "self consuming script"
    #
    # I know, I know... pretty clever shit here... I got the idea from here:
    # https://superuser.com/questions/365452/how-to-write-awk-here-document
    # The head and tail thing is to remove the #BEGIN_XX and #END_XX lines
    # that result from the plain sed.
    sed -e "/#[B]EGIN_$1/,/#[E]ND_$1/!d" $0 | head -n-1 | tail -n+2
}


# find the minimum time gap between sequential events
find_gap(){
    # temporary C file where to dump the benchmark code defined
    # at the end of this script, and temp file where to store
    # the compiled version of that program
    local tmp_c_file=$(mktemp /tmp/benchmark-XXXXX.c)
    local tmp_bin_file=$(mktemp /tmp/benchmark-XXXXX.bin)
    echo -e "$(embedded_file C1)" > $tmp_c_file
    gcc -Wall -O0 -g -o "$tmp_bin_file" "$tmp_c_file"

    # where to store the pintool output
    local tmp_log_file=$(mktemp /tmp/benchmark-XXXXX.log)

    # the program pin and the pintool mem_tracer.so must be in the $PATH,
    # otherwise this script cannot benchmark anything. So make sure of adding
    # them to $PATH
    if ! which pin &>/dev/null; then
        echo "'pin' not found." >&2
        exit 1
    fi
    local mem_tracer_path="$(which mem_tracer.so 2>/dev/null)"
    if [[ ! -f "$mem_tracer_path" ]]; then
        echo "'pintool' mem_tracer.so not found." >&2
        exit 1
    fi
    pin -t "$mem_tracer_path" -o "$tmp_log_file" -- "$tmp_bin_file"

    # analyze the output to determine the minimum sequential time
    # difference.
    local min_seq_gap=$(awk -f \
                        <(embedded_file AWK_GET_MIN) \
                        <(tail -n+8 "$tmp_log_file"))

    # Ok, this is the part I pull out of my ass: let's just take 0.66 of that
    # value, just to be sure that those "concurrent events" were really
    # concurrent, and not an unusually quick sequential events.
    # The worst that can happen is that the events were actually concurrent,
    # but they were registered as sequential: nothing explodes. But if
    # sequential events are taken as parallel, then you will look at the
    # resulting data for hours and say:
    #              "why the fuck that element is accessed at the
    #              same time as this other one, it makes no sense"
    # start screaming into the void, and question your life decisions...
    # Actually those many hours of life crisis made me find this issue and made
    # me come up with this whole timestamp -> total order thing. So, yeah...
    echo $(($min_seq_gap * 667 / 1000))

}

convert_log(){
    if [[ $# -ne 2 ]]; then
        echo "$(basename "$0"):convert: ERROR: this subcommand"\
            "needs two arguments."
        print_help
        exit 1
    fi
    local gap="$1" log="$2"
    if [[ ! -f "$log" ]]; then
        echo "$(basename "$0"):convert: ERROR: file '$log' does not exist."
        print_help
        exit 1
    fi


    # save header and data in two different files
    local tmp_header=$(mktemp /tmp/mem_trace_header-XXXXX.log)
    local tmp_data=$(mktemp /tmp/mem_trace_data-XXXXX.log)
    local -i header_end=$(awk '{if($0 == "TRACE_DATA_START")print NR}' "$log")
    head -n$((header_end+1)) "$log" > "$tmp_header"
    tail -n+$((header_end+2)) "$log" | sort -n > "$tmp_data"

    # re-compose the log file by concatenating the header file with the new
    # data file that has had replaced the timestamps.
    cat $tmp_header \
        <(awk -v GAP="$gap" -f <(embedded_file AWK_CONVERT) "$tmp_data") \
        | sed "s/##GAP_VALUE##/$gap/"

    return
}

print_help(){
    cat <(embedded_file HELP) >&2
}


case "$1" in
    "find-gap")
        shift
        find_gap "$@"
        ;;
    "convert")
        shift
        convert_log "$@"
        ;;
    *)
        print_help
esac
exit 0


# ----------------- START OF EMBEDDED FILES -----------------------
# Help message
#BEGIN_HELP
    USAGE: tracequantizer find-gap
           tracequantizer convert <gap> <input mem_trace log>
#END_HELP




# The pintool mem_trace.so records each event with its timestamp. This
# timestamp is on the nano-seconds order, and it is a good way to sort which
# events happened before or after. In a sequential program, the events are
# naturally sorted such that their timestamps go from the smallest to the
# largest.
#
# However, when we have a multi-threaded setup, many threads could concurrently
# register events at their own timing, resulting in a final list of events at
# pretty much the same time. Now, the key word here is "pretty much".
#
# Tracing the memory usage is all about finding the total order of events, not
# the "actual time" they happened. If event 0 happenend at noon and event 1 at
# 3pm, we just care that event 0 happened before event 1. So it is important to
# determine how quickly can a thread produce two consecutive accesses to memory.
# This will be our "time unit". Anything that happens quicker than that will be
# considered as "happening at the same time".
#
# If the fastest a thread can issue two events is, let's say, every 1000ns, and
# two events (from thread0 and thread1) are registered with 300ns of difference,
# then they can be considered to have happened concurrently.
#
# The following program benchmarks the executing machine to determine how
# quickly a given thread can issue two sequential memory accesses.
# This value will then be used to quantize the timestamps in other experiments.

#BEGIN_C1
#include <stdio.h>
#include <stdlib.h>

// content of instr.h. Just copied here for practical reasons
//#include "instr.h"
void __attribute__((optimize("O0")))
instr_select_next_block(void) {}
void __attribute__((optimize("O0")))
instr_start_tracing(void) {}
void __attribute__((optimize("O0")))
instr_stop_tracing(void) {}

unsigned int N=128;

int main(void){
    volatile double *chunk;
    instr_select_next_block();
    chunk = malloc(N * sizeof(double));
    if(!chunk)
        return 1;
    double x;
    unsigned int i, j;
    instr_start_tracing();
    for(i=0; i<8; i++)
        for(j=0; j<N; j++)
           x = chunk[j];
    instr_stop_tracing();
    x = x+1; // to avoid compiler magic
    free((double *)chunk);
    return 0;
}
#END_C1



# This script computes the difference between each pair of consecutive
# timestamps, and reports the minimum difference found.
#BEGIN_AWK_GET_MIN
#!/bin/env awk
BEGIN{
    FS=","
    min_diff=999999999999999;
}
NR == 1 {
    prev=$1
}
NR > 1 {
    curr=$1;
    diff=curr - prev
    prev=curr
    #printf("%s %d\n", $0, diff)
    if(min_diff > diff)
          min_diff=diff
}
END {
    printf("%d\n",min_diff)
}
#END_AWK_GET_MIN



# This script changes the nanosecond timestamps into small integers
# that show the relative order among elements.
#BEGIN_AWK_CONVERT
#!/bin/env awk
BEGIN{
    counter=-1
    base=0
    FS=","
}
{
    current=$1;
    diff = current - base
    printf("base:%d,curr:%d,diff:%d,",
           base,current,diff)
    if(diff > GAP){
      counter += 1
      base = current
    }
    printf("%d,%d,%s,%d,%d\n",counter,$2,$3,$4,$5)

}
END{
}
#END_AWK_CONVERT
