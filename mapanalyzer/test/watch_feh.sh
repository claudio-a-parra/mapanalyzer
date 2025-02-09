#!/bin/bash
while true; do
    feh -.Zr -B '#00000' --on-last-slide hold 03-plots/* &>/dev/null
    feh -.Zr -B '#00000' --on-last-slide hold 04-aggr/* &>/dev/null
    #echo -en '\rScan again?'
    #read -n 1
    sleep 0.5
done
