#!/bin/bash

cr_dir=00-source
maps_dir=01-maps
pdata_dir=02-pdata
plot_dir=03-plots
aggr_dir=04-aggr

clean_all(){
    rm -rf ./$maps_dir/*
    rm -rf ./$pdata_dir/*
    rm -rf ./$plot_dir/*
    rm -rf ./$aggr_dir/*
    flag_tree
}

create_quicksort(){
    local map_id=$1
    local min_len=$2
    local max_len=$3
    if [[ "$max_len" == "" ]]; then
        max_len=$min_len
    fi
    local alg=quicksort_pthread

    list_len=$(($min_len + $RANDOM % ($max_len - $min_len + 1)))
    list_len=$(printf "%0${#max_len}d" $list_len)

    make \
        source=$alg.c \
        algorithm=$alg \
        binary_args="$list_len $map_id" \
        access_pattern="$alg-$map_id-$list_len.map" \
        map
    return
}
create_convergent(){
    local map_id=$1
    local min_len=$2
    local max_len=$3
    if [[ "$max_len" == "" ]]; then
        max_len=$min_len
    fi
    local alg=conv-rand

    list_len=$(($min_len + $RANDOM % ($max_len - $min_len + 1)))
    list_len=$(printf "%0${#max_len}d" $list_len)

    make \
        source=$alg.c \
        algorithm=$alg \
        binary_args="$list_len $map_id" \
        access_pattern="$alg-$map_id-$list_len.map" \
        map
    return
}
create_convolution(){
    local map_id=$1
    local ker_size=$2
    local min_size=$3
    local max_size=$4
    if [[ "$max_size" == "" ]]; then
        max_size=$min_size
    fi
    local alg=convolution

    mat_size=$(($min_size + $RANDOM % ($max_size - $min_size + 1)))
    mat_size=$(printf "%0${#max_size}d" $mat_size)

    make \
        source=$alg.c \
        algorithm=$alg \
        binary_args="$mat_size $ker_size" \
        access_pattern="$alg-$map_id-$mat_size-$ker_size.map" \
        map
    return
}

create_maps(){
    clean_all
    # create map files
    cd $cr_dir || exit 1
    make clean
    local kind="$1" && shift
    local num_maps="$1" && shift

    for ((m=1; m<=$num_maps; m++)); do
        map_id=$(printf "%0${#num_maps}d" $m)
        create_$kind $map_id "$@"
        flag_tree
    done

    cd ..

    # move maps to separated folder
    mkdir -p ./$maps_dir
    if ls ./$cr_dir/*.map &>/dev/null; then
        rm -rf ./$maps_dir/*
        mv $cr_dir/*.map ./$maps_dir/
    else
        echo -e "\n\nTEST.create_maps($num_maps, $min_lsize, $max_lsize): " \
            "MAP files not created!"
        flag_tree
        exit 1
    fi
    flag_tree
}
mtest(){
    local mode="$1"
    shift
    local command_options="$@"

    # clear whatever byproduct there is in current dir
    rm -rf ./*.json ./*.png ./*.pdf

    # select the input directory based on the mode
    if [[ "$mode" = "simulate" || "$mode" == "sim-plot" ]]; then
        local input_data=$maps_dir/'*.map'
    else
        local input_data=$pdata_dir/'*.json'
    fi

    # run mapanalyzer
    if ls ./$maps_dir/*.map &>/dev/null; then
        local command=(mapanalyzer --mode $mode $command_options
                       ${common_opts[@]} -- ./"$input_data")
        echo "${command[@]}"
        eval "${command[@]}"
    else
        echo -e "\n\nTEST.mtest(--mode $mode $command_options): MAP files " \
            "not found in ./$maps_dir/"
        flag_tree
        exit 1
    fi
    flag_tree

    # move json files to a separated folder
    if [[ "$mode" = "simulate" || "$mode" = "sim-plot" ]]; then
        mkdir -p ./$pdata_dir
        rm -rf ./$pdata_dir/*
        if ls ./*.json &>/dev/null; then
            mv ./*.json ./$pdata_dir/
        else
            echo -e "\n\nTEST.mtest(--mode $mode $command_options): JSON " \
                "files not created!"
            flag_tree
            exit 1
        fi
    fi
    flag_tree

    # move plot files to a separated folder
    if [[ "$mode" = "sim-plot" || "$mode" = "plot" || "$mode" = "aggregate" ]]; then
        local fig_dir=$plot_dir
        if [[ "$mode" = "aggregate" ]]; then
            local fig_dir=$aggr_dir
        fi

        mkdir -p ./$fig_dir
        rm -rf ./$fig_dir/*
        if ls ./*.png &>/dev/null; then
            mv ./*.png ./$fig_dir/
        elif ls ./*.pdf &>/dev/null; then
            mv ./*.pdf ./$fig_dir/
        else
            echo -e "\n\nTEST.mtest(--mode $mode $command_options): PLOT " \
                "files not created!"
            flag_tree
            exit 1
        fi
    fi
    flag_tree
}
view(){
    while true; do
         feh -qrxZ. -B 'black' --on-last-slide hold ./$plot_dir/
         feh -qrxZ. -B 'black' --on-last-slide hold ./$aggr_dir/
         sleep 1
    done
}
flag_tree(){
    touch .flag_tree
}
create_cache(){
    cat <<EOF > cache.conf
line_size_bytes  : 4
associativity    : 2
cache_size_bytes : 32
arch_size_bits   : 64
EOF
    bat cache.conf
}
size=(-pw 8 -ph 6.5)
size=(-pw 11 -ph 20)
common_opts=(${size[@]} --dpi 400 --cache cache.conf)
METS=MAP,SLD,TLD,CMR,CMMA,CUR,AD,BPA,SMRI,MRID
METS=MRID
MODE=plot


clear
#create_maps quicksort 2 40
#create_maps convergent 2 2000000
#create_maps convolution 2 3 400 500

#create_cache
mtest $MODE -mc $METS
#mtest aggregate -mc $METS
echo -e "\n\nTEST: Done"
