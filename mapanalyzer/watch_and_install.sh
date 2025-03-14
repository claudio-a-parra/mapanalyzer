#!/usr/bin/env sh

set -e

install_mapanalyzer(){
    set-alacritty-title "..."
    if make install; then
        set-alacritty-title "INSTALLER OK"
    else
        set-alacritty-title "INSTALLER ERROR"
    fi
}

export -f install_mapanalyzer
clear
set-alacritty-title "INSTALLER WAITING"
(find ./mapanalyzer -type f | entr -pc bash -c 'install_mapanalyzer')
set-alacritty-title "INSTALLER EXIT"
