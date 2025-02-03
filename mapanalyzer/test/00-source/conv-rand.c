#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <maptracer.h>

size_t rand_normal_range(size_t min, size_t max, double mean, double stddev) {
    // Generate two uniform random numbers between 0 and 1
    double u1 = ((double) rand() / RAND_MAX);
    double u2 = ((double) rand() / RAND_MAX);
    // Box-Muller transform to generate a normal distribution (mean = 0, stddev = 1)
    double z0 = sqrt(-2.0 * log(u1)) * cos(2.0 * M_PI * u2);

    // Scale by standard deviation and shift by mean
    double result = mean + z0 * stddev;

    // Map to integer range [min, max]
    if (result < min) result = min;
    if (result > max) result = max;

    return (size_t) round(result);
}

int main(int argc, char *argv[]) {
    // parse command line arg and init random seed
    size_t size, seed;
    if(argc == 2){
        size = atoi(argv[1]);
        seed = 0;
    } else if (argc == 3){
        size = atoi(argv[1]);
        seed = atoi(argv[2]);
    }else{
        fprintf(stderr,"USAGE: %s <array_size> [rand_seed]\n", argv[0]);
        exit(1);
    }
    srand(seed);

    mt_select_next_block();
    //char *A = (char*) aligned_malloc(size * sizeof(char), 16);

    size_t addr;
    volatile char xor=0;
    char *A = (char*) malloc(size*sizeof(char));
    mt_start_tracing();

    for(size_t i=0; i<size; i++){
        addr = rand_normal_range(0, size, size/2, (size-i)/6);
        xor ^= A[addr];
    }

    mt_stop_tracing();
    free(A);
    //aligned_free(A);

    return 0;
}
