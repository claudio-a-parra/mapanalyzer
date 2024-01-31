// example.c
// Have two threads modifying a piece of data in an alternating fashion.
// They use pthread_locks to make sure they interleave their work.
#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include "instr.h"

int N=512;
int shared=0;
pthread_mutex_t m;
volatile double *chunk;

void *thread_work(void* tid){
    int id = *((int*) tid);
    for(int i=0; i<N; i++){
        while(1){
            pthread_mutex_lock(&m);
            if(shared%2==id){
                chunk[i] = i;
                shared += 1;
                pthread_mutex_unlock(&m);
                break;
            }
            pthread_mutex_unlock(&m);
        }
    }
    return NULL;
}

int main(void){
    pthread_mutex_init(&m,NULL);

    instr_select_next_block();
    chunk = malloc(N * sizeof(double));
    if(!chunk){
        printf("allocation failed\n");
        return 1;
    }

    instr_start_tracing();

    int id0=0, id1=1;
    pthread_t t0, t1;
    pthread_create(&t0, NULL, &thread_work, (void*)&id0);
    pthread_create(&t1, NULL, &thread_work, (void*)&id1);

    pthread_join(t0,NULL);
    pthread_join(t1,NULL);

    instr_stop_tracing();

    free((double *)chunk);

    return 0;
}
