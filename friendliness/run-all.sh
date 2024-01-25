#!/bin/bash
clear
if [[ $0 -gt 0 ]]; then
    win=" -w $1"
else
    win=""
fi
rm -- *.png
for i in *.map; do
    echo "---  $i  ------------------------------------"
    ./scripts/main.py"$win" "$i"

done
