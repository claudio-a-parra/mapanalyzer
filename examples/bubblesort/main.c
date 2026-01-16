#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <stddef.h>
#include <maptracer.h>

void bubblesort(int *L, size_t L_len){
    unsigned char swapped = 1; int tmp;
    while(swapped){
        swapped = 0;
        for(size_t i=0; i<L_len-1; i++){
            if(L[i] > L[i+1]){
                tmp = L[i];
                L[i] = L[i+1];
                L[i+1] = tmp;
                swapped = 1;
            }
        }
    }
    return;
}

void fill_example(int *L, size_t L_len){
    int pro_l[] = {1, 6, 3, 2, 4, 5};
    for(size_t i=0; i<L_len; i++){
        L[i] = pro_l[i];
    }
}

void fill_random(int *L, size_t L_len){
    for(size_t i=0; i<L_len; i++){
        L[i] = rand()%(10*L_len);
    }
}

void print(int *L, size_t L_len){
    for(size_t i=0; i<L_len; i++){
        printf("%d ", L[i]);
    }
    printf("\n");
}

int main(int argc, char **argv) {
    // parse command line arg and init random seed
    size_t L_len, seed;
    if(argc == 2){
    L_len = atoi(argv[1]);
        seed = time(NULL);
    } else if (argc == 3){
        L_len = atoi(argv[1]);
        seed = atoi(argv[2]);
    }else{
        fprintf(stderr,"ERROR: usage: %s <list_size> [rand_seed]\n", argv[0]);
        exit(1);
    }
    srand(seed);


    mt_select_next_block();
    //int *L = (int*)aligned_malloc(L_len*sizeof(int), 64);
    int *L = (int*)malloc(L_len*sizeof(int));
    if(L_len == 6){
        fill_example(L, L_len);
    }else{
        fill_random(L, L_len);
    }

    mt_start_tracing();
    bubblesort(L, L_len);
    mt_stop_tracing();
    //aligned_free(L);
    free(L);
    return 0;
}
