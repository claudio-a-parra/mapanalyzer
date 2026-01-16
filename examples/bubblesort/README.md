# Simple bubble-sort
This simple example obtains the MAP of bubble-sort.

## The bubble sort program
Its usage is quite simple:

``` shell
./bubblesort <list_size> [rand_seed]
```

Or directly from the `Makefile`:

``` shell
make LS=<list_size> RS=[rand_seed] run
```

If `list_size` is 6, then the array is filled exactly with `{1, 6, 3, 2, 4, 5}`. (just to reproduce the diagram shown below)

## Obtaining the MAP
Simply running the bubblesort program won't give us its MAP, we need to run it from pin with `maptracer`.

### Instrumenting
To instrument a region of the execution, first we add four lines to the code:

``` c
//...
#include <maptracer.h>      // <-- Include the maptracer library
//...
int main(int argc, char **argv) {
    //...
    mt_select_next_block(); // <-- Tell maptracer that we will focus
                            //     on the memory region returned by 
                            //     the next malloc.
    int *L = (int*)malloc(L_len*sizeof(int));
    //...
    mt_start_tracing();     // <-- Start collecting memory access
                            //     operations in that region.
    bubblesort(L, L_len);
    mt_stop_tracing();      // <-- Stop collecting data.
    //...
}
```

(For full details, refer to the 4th chapter of the thesis.)

### 
