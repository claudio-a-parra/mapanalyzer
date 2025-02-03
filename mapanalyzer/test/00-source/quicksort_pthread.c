#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <pthread.h>
#include <maptracer.h>

int partition(char *list, int L, int H){ // never called for size < 2
    char pvt = list[H], tmp;
    int l=L, h=H-1;
    while(l < h){
        if(list[l] <= pvt){
            l++;
            continue;
        }
        if(list[h] > pvt){
            h--;
            continue;
        }
        // at this point, list[l] > pvt, and list[h] <= pvt. Swap them.
        tmp = list[l];
        list[l] = list[h];
        list[h] = tmp;
        l++;
        h--;
    }
    // if l & h crossed, then l is pointing to something greater than pivot
    // Therefore, I should swap the pivot (last element) with list[l] and
    // return the pivot index, which now is l
    if(h < l){
        tmp = list[l];
        list[l] = list[H];
        list[H] = tmp;
        return l;
    }

    // if h & l point to the same element, check whether it is greater than
    // the pivot, if so, swap and return the pivot's index.
    if(h == l && list[l] > pvt){
        tmp = list[l];
        list[l] = list[H];
        list[H] = tmp;
        return l;
    }

    // if h & l point to the same element, BUT list[l] is smaller or equal to
    // the pivot, then move l one to the right, and swap that with the pivot.
    if(h == l && list[l] <= pvt){
        l++;
        tmp = list[l];
        list[l] = list[H];
        list[H] = tmp;
        return l;
    }

    return l;
}

void quick_sort(char *list, int L, int H){
    // check indices
    if (H <= L || L < 0)
        return;

    // get pivot index
    int pvt_idx = partition(list, L, H);
    quick_sort(list, L, pvt_idx-1);
    quick_sort(list, pvt_idx+1, H);
}

typedef struct {
    char *list;
    int low;
    int high;
} Qs;

void *qsort_thread(void* arg){
    quick_sort(((Qs*)arg)->list, ((Qs*)arg)->low, ((Qs*)arg)->high);
    pthread_exit(NULL);
    return NULL;
}

int main(int argc, char *argv[]) {
    // parse command line arg and init random seed
    size_t list_size;
    int seed;
    if(argc == 2){
        list_size = atoi(argv[1]);
        seed = time(NULL);
    } else if (argc == 3){
        list_size = atoi(argv[1]);
        seed = atoi(argv[2]);
    }else{
        fprintf(stderr,"ERROR: usage: %s <list_size> [rand_seed]\n", argv[0]);
        exit(1);
    }
    srand(seed);


    // create and populate list
    mt_select_next_block();
    char *list = (char *)malloc(list_size);
    for(size_t i=0; i<list_size; i++)
        list[i] = rand()%(10*list_size);

    // store original list in file "A"
    // FILE *unsorted = fopen("A","w");
    // for(int i=0; i<list_size; i++)
    //     fprintf(unsorted, "%d\n", list[i]);

    // pass half of the list to each thread.
     Qs qs0, qs1;
     pthread_t t0,t1;
     qs0 = (Qs){list, 0, (list_size/2)-1};
     qs1 = (Qs){list, list_size/2, list_size-1};

    mt_start_tracing();

    /* quick_sort(list, 0, list_size-1); */

    /* qsort_thread((void*)&qs0); */
    /* qsort_thread((void*)&qs1); */

    pthread_create(&t0, NULL, &qsort_thread, &qs0);
    pthread_create(&t1, NULL, &qsort_thread, &qs1);

    pthread_join(t0,NULL);
    pthread_join(t1,NULL);

    mt_stop_tracing();

    // store resulting list in file "B"
    // FILE *sorted = fopen("B","w");
    // for(int i=0; i<list_size; i++)
    //    fprintf(sorted, "%d\n", list[i]);

    pthread_exit(NULL);
}
