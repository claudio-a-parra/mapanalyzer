#!/bin/bash

test_mapanalyzer(){
    set-alacritty-title "MAPANALIZER-TEST: ..."
    if ./test.sh; then
        set-alacritty-title "MAPANALIZER-TEST: OK"
    else
        set-alacritty-title "MAPANALIZER-TEST: ERROR"
    fi
    touch .flag_ready

}

export -f test_mapanalyzer

clear
set-alacritty-title "MAPANALIZER-TEST: WAITING"
/bin/ls test.sh .flag_installed | entr -pc bash -c 'test_mapanalyzer'
set-alacritty-title "MAPANALIZER-TEST: EXIT"
