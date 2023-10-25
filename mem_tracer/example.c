// example.c
#include <stdio.h>
#include <stdlib.h>
#include "instr.h"

unsigned int N=256;

int main(void){
    volatile double *chunk;

    instr_select_next_block();
    chunk = malloc(N * sizeof(double));

    if(!chunk){
        printf("allocation failed\n");
        return 1;
    }

    double x;
    unsigned int i;
    instr_start_tracing();

    for(i=0; i<N; i++)
        x = chunk[i];
    for(i=0; i<N; i++)
        x = chunk[i];
    for(i=0; i<N; i++)
        x = chunk[i];
    for(i=0; i<N; i++)
        x = chunk[i];

    instr_stop_tracing();

    x = x+1;

    free((double *)chunk);

    return 0;
}
