#!/bin/bash

view_results(){
    while true; do
        plot_pid=no-pid
        aggr_pid=no-pid
        set-alacritty-title "RESULTS: SCANNING"
        sleep 1

        # check for plots
        if ls ./03-plots/*.png &>/dev/null; then
            set-alacritty-title "RESULTS: SHOWING IMAGES..."
            feh -.Zr -B '#00000' --title 'PLOTS: [%u/%l] %n' --auto-reload --on-last-slide hold ./03-plots &>/dev/null &
            plot_pid=$!
            sleep 0.5
        fi

        # check for aggregated plots
        if ls ./04-aggr/*.png &>/dev/null; then
            set-alacritty-title "RESULTS: SHOWING IMAGES..."
            feh -.Zr -B '#00000' --title 'AGGR: [%u/%l] %n' --auto-reload --on-last-slide hold ./04-aggr &>/dev/null &
            aggr_pid=$!
            sleep 0.5
        fi

        # wait for feh to be killed
        if [[ "$plot_pid" != no-pid || "$aggr_pid" != no-pid ]]; then
            set-alacritty-title "RESULTS: WAITING"
            while kill -0 $plot_pid &>/dev/null || kill -0 $aggr_pid &>/dev/null; do
                sleep 0.5
            done
        fi
    done
}

cleanup(){
    set-alacritty-title "RESULTS: EXIT"
}
trap cleanup SIGINT
clear
view_results
