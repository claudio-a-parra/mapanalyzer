#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <maptracer.h>

static inline char *allocate_char_matrix(int size) {
    return (char *)malloc(size * size * sizeof(char));
}

void initialize_matrix(char *matrix, int size) {
    srand(time(NULL));
    for (int i = 0; i < size * size; i++) {
        matrix[i] = rand() % 256;  // Random char value
    }
}

void initialize_kernel(int *kernel, int kernel_size) {
    // A simple averaging kernel.
    for (int i = 0; i < kernel_size * kernel_size; i++)
        kernel[i] = 1;
}

void print_matrix(char *matrix, int size) {
    for (int i = 0; i < size; i++) {
        for (int j = 0; j < size; j++) {
            printf("%3d ", (unsigned char)matrix[i * size + j]);
        }
        printf("\n");
    }
}

void convolution(char *matrix, char *result, int matrix_size, int kernel_size) {
    // slide kernel across matrix.
    int offset = kernel_size / 2;
    for (int i = offset; i < matrix_size - offset; i++) {
        for (int j = offset; j < matrix_size - offset; j++) {
            int sum = 0;
            for (int ki = -offset; ki <= offset; ki++) {
                for (int kj = -offset; kj <= offset; kj++) {
                    sum += (unsigned char)matrix[(i + ki) * matrix_size + (j + kj)];
                }
            }
            result[i * matrix_size + j] = sum / (kernel_size*kernel_size);
        }
    }
}

int main(int argc, char *argv[]) {
    if (argc != 3) {
        fprintf(stderr, "Usage: %s <matrix_size> <kernel_size>\n", argv[0]);
        return 1;
    }

    int matrix_size = atoi(argv[1]);
    int kernel_size = atoi(argv[2]);

    if (kernel_size % 2 == 0 || kernel_size > matrix_size) {
        fprintf(stderr, "Kernel size must be an odd number and less than or "
                "equal to matrix size.\n");
        return 1;
    }

    mt_select_next_block();
    char *matrix = allocate_char_matrix(matrix_size);
    char *result = allocate_char_matrix(matrix_size);

    initialize_matrix(matrix, matrix_size);

    //printf("Original Matrix:\n");
    //print_matrix(matrix, matrix_size);

    mt_start_tracing();
    convolution(matrix, result, matrix_size, kernel_size);
    mt_stop_tracing();

    //printf("\nConvoluted Matrix:\n");
    //print_matrix(result, matrix_size);

    free(matrix);
    free(result);
    return 0;
}
