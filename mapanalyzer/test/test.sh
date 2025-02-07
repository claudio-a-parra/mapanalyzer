#!/bin/bash
set -e
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
    tree_flag
}
create_maps(){
    clean_all
    # create map files
    cd $cr_dir || exit 1
    make clean
    num_maps=$1
    min_lsize=$2
    max_lsize=$3
    if [[ "$max_lsize" == "" ]]; then
        max_lsize=$min_lsize
    fi
    max_seed=99
    for ((m=1; m<=$num_maps; m++)); do
        rand_list_size=$(($min_lsize + $RANDOM \
            % ($max_lsize - $min_lsize + 1)))
        rand_list_size=$(printf "%0${#max_lsize}d" $rand_list_size)
        #rand_seed=$(printf "%0${#max_seed}d" $(($RANDOM % ($max_seed + 1))))
        rand_seed=$(printf "%0${#max_seed}d" $(($m % ($max_seed + 1))))
        make LIST_LEN=$rand_list_size SEED=$rand_seed map || exit 1
        tree_flag
    done
    cd ..

    # move maps to separated folder
    mkdir -p ./$maps_dir
    if ls ./$cr_dir/*.map &>/dev/null; then
        rm -rf ./$maps_dir/*
        mv $cr_dir/*.map ./$maps_dir/
    else
        echo -e "\n\nTEST.create_maps($num_maps, $min_lsize, $max_lsize): MAP files not created!"
        tree_flag
        exit 1
    fi
    tree_flag
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
        tree_flag
        exit 1
    fi
    tree_flag

    # move json files to a separated folder
    if [[ "$mode" = "simulate" || "$mode" = "sim-plot" ]]; then
        mkdir -p ./$pdata_dir
        rm -rf ./$pdata_dir/*
        if ls ./*.json &>/dev/null; then
            mv ./*.json ./$pdata_dir/
        else
            echo -e "\n\nTEST.mtest(--mode $mode $command_options): JSON " \
                "files not created!"
            tree_flag
            exit 1
        fi
    fi
    tree_flag

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
            tree_flag
            exit 1
        fi
    fi
    tree_flag
}
view(){
    while true; do
         feh -qrxZ. -B 'black' --on-last-slide hold ./$plot_dir/
         feh -qrxZ. -B 'black' --on-last-slide hold ./$aggr_dir/
         sleep 1
    done
}
tree_flag(){
    touch .flag_tree
}
create_cache(){
    cat <<EOF > cache.conf
line_size_bytes  : 2
associativity    : 1
cache_size_bytes : 4
arch_size_bits   : 64
EOF
    bat cache.conf
}

common_opts=(-pw 8 -ph 4 --dpi 300 --cache cache.conf)
METS=MAP,SLD,TLD,CMR,CMMA,CUR,AD
METS=MAP,AD

clear
create_cache

#create_maps 3 12
#mtest sim-plot --metrics MAP,$METS
mtest aggregate --metrics AD
#echo -e "\n\nTEST: Done"
