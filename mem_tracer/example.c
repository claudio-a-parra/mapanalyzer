// example.c
#include <stdio.h>
#include <stdlib.h>
#include "instr.h"
#define N 12

int main(void){
    volatile double *chunk;

    instr_select_next_block();

    chunk = malloc(N * sizeof(double));

    if(!chunk){
        printf("alloc failed\n");
        return 1;
    }

    instr_start_tracing();

    for(unsigned i = 0; i < N; i++)
        chunk[i] += (double)(100+i);

    instr_stop_tracing();

    free((double *)chunk);

    return 0;
}
