
# CONVERGENT RANDOM
# source = conv-rand.c
# algorithm := conv-rand
# LIST_LEN = 100
# SEED = 0
# cclibs = -lm
# binary_args = $(LIST_LEN) $(SEED)
# access_pattern = $(algorithm)-$(LIST_LEN)-$(SEED).map

# QUICKSORT
# source := quicksort_pthread.c
# algorithm := quicksort_pthread
# LIST_LEN = 100
# SEED = 0
# cclibs = -lm -lpthread
# binary_args = $(LIST_LEN) $(SEED)
# access_pattern = $(algorithm)-$(LIST_LEN)-$(SEED).map

# QUICKSORT
source := convolution.c
algorithm := convolution
MAT_SIZE = 10
KER_SIZE = 3
binary_args = $(MAT_SIZE) $(KER_SIZE)
access_pattern = $(algorithm)-$(MAT_SIZE)-$(KER_SIZE).map


#-------------------------


define HELP_ABOUT
	$(algorithm)
endef
export HELP_ABOUT
define HELP_VARIABLES
    LIST_LEN : ($(LIST_LEN)) length of the list to be accessed.
	SEED: ($(SEED)) seed for random number generator.
endef
export HELP_VARIABLES

include include_experiment.mk
