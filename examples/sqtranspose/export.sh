#!/usr/bin/env bash
# cd directory of this script, and fix timestamp
cd -- "$(dirname "$0")"
timestamp=$(date +%Y%m%d_%H%M%S)

metrics=MAP,SLD,TLD,CMR

echo -e "\033[1mEXPORT START: $0\033[0m"
make ALG=n timestamp=$timestamp \
    MA_METRICS=$metrics \
    build map plot
make ALG=r timestamp=$timestamp \
    MA_METRICS=$metrics \
    build map plot
echo -e "\033[1mEXPORT END  : $0\033[0m"

