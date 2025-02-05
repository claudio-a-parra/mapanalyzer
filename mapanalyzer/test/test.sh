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

simulate(){
    local command_options="$@"
    # create json files
    if ls ./$maps_dir/*.map &>/dev/null; then
        local command=(mapanalyzer --mode simulate $command_options
                       -- ./$maps_dir/'*.map')
        echo "${command[@]}"
        eval "${command[@]}"
    else
        echo -e "\n\nTEST.simulate($command_options): MAP files not " \
            "found in ./$maps_dir/"
        tree_flag
        exit 1
    fi

    # move json files to a separated folder
    mkdir -p ./$pdata_dir
    rm -rf ./$pdata_dir/*
    if ls ./*.json &>/dev/null; then
        mv ./*.json ./$pdata_dir/
    else
        echo -e "\n\nTEST.simulate($command_options): JSON files not " \
            "created!"
        tree_flag
        exit 1
    fi

    if [[ "$mode" = "sim-plot" ]]; then
        # move plot files to a separated folder
        mkdir -p ./$plot_dir
        rm -rf ./$plot_dir/*
        if ls ./*.png &>/dev/null; then
            mv ./*.png ./$plot_dir/
        elif ls ./*.pdf &>/dev/null; then
            mv ./*.pdf ./$plot_dir/
        else
            echo -e "\n\nTEST.simulate($command_options): PLOT files " \
                "not created!"
            tree_flag
            exit 1
        fi
    fi
    tree_flag
}

plot(){
    local command_options="$@"
    # create plots
    if ls ./$pdata_dir/*.json &>/dev/null; then
        local command=(mapanalyzer --mode plot $command_options
                       -- ./$pdata_dir/'*.json')
        echo "${command[@]}"
        eval "${command[@]}"
    else
        echo -e "\n\nTEST.plot($command_options): JSON files not found in ./$pdata_dir/"
        tree_flag
        exit 1
    fi

    # move plot files to a separated folder
    mkdir -p ./$plot_dir
    rm -rf ./$plot_dir/*
    if ls ./*.png &>/dev/null; then
        mv ./*.png ./$plot_dir/
    elif ls ./*.pdf &>/dev/null; then
        mv ./*.pdf ./$plot_dir/
    else
        echo -e "\n\nTEST.plot($command_options): PLOT files not created!"
        tree_flag
        exit 1
    fi
    tree_flag
}

aggregate(){
    local command_options="$@"
    # aggregate plots
    if ls ./$pdata_dir/*.json &>/dev/null; then
        local command=(mapanalyzer --mode aggregate $command_options
                       ./$pdata_dir/'*.json')
        echo "${command[@]}"
        eval "${command[@]}"
    else
        echo -e "\n\nTEST.agreggate($command_options): JSON files not found in ./$pdata_dir/"
        tree_flag
        exit 1
    fi

    # move plot files to a separated folder
    mkdir -p ./$aggr_dir
    rm -rf ./$aggr_dir/*
    if ls ./*.png &>/dev/null; then
        mv ./*.png ./$aggr_dir/
    elif ls ./*.pdf &>/dev/null; then
        mv ./*.pdf ./$aggr_dir/
    else
        echo -e "\n\nTEST.aggregate($command_options): PLOT files not created!"
        tree_flag
        exit 1
    fi
    tree_flag
}

view(){
    if [[ "$1" = "plot" ]]; then
        which_dir=$plot_dir
    elif [[ "$1" = "aggr" ]]; then
        which_dir=$aggr_dir
    else
        echo -e "\n\nTEST.view($1): Unknown option (use 'plot' or 'aggr')"
        tree_flag
        exit 1
    fi

    # view results
    tree_flag
    if ls ./$which_dir/*.png; then
        feh -qrxZ. -B 'black' ./$which_dir &
    elif ls ./$which_dir/*.pdf; then
        pdftk ./$which_dir/*.pdf cat output ./$which_dir/__all_plots.pdf
        evince ./$which_dir/__all_plots.pdf &
    fi
}

tree_flag(){
    touch .flag_tree
}

clear

#create_maps 3 5000
#simulate  --metrics CMMA,CUR,CMR --cache cache.conf || exit 1
plot      --metrics CMMA,CUR,CMR -pw  8 -ph  8 --dpi 400 || exit 1
aggregate --metrics CMMA,CUR,CMR -pw 8 -ph 8 --dpi 400 || exit 1
#view plot

echo -e "\n\nTEST: Done"
