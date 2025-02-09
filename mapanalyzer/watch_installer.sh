#!/usr/bin/env sh

set -e

set-alacritty-title "..."
if make install; then
    set-alacritty-title "INSTALLER OK"
    touch ./test/.flag_installed
else
    set-alacritty-title "INSTALLER ERROR"
fi
