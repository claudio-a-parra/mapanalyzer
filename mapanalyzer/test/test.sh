#!/bin/bash
source ./test.source
clear

size=(-pw 11 -ph 20)
size=(-pw 8 -ph 6.5)
common_opts=(${size[@]} --dpi 200 --cache cache.conf)
METS=MAP,SLD,TLD,CMR,CMMA,CUR,AD,BPA,SMRI,MRID
METS=MAP,BPA,SMRI,MRID
METS=MRID
MODE=(simulate aggregate)

#clear_all
create_maps quicksort 50 10000 20000
#create_maps convergent 50 20000 40000
#create_maps convolution 2 3 400 500

#create_cache 4 2 32
for M in ${MODE[@]}; do
    mtest $M -mc $METS -bm MAP -Pi
done
echo -e "\n\nTEST: Done"
