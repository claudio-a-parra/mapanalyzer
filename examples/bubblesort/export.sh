#!/usr/bin/env bash
# cd directory of this script, and fix timestamp
cd -- "$(dirname "$0")"
timestamp=$(date +%Y%m%d_%H%M%S)

metrics=MAP
width=12

echo -e "\033[1mEXPORT START: $0\033[0m"
make LS=6 RS=0 timestamp=$timestamp \
    MA_METRICS=$metrics\
    MA_WIDTH=$width \
    build map plot
echo -e "\033[1mEXPORT END  : $0\033[0m"
