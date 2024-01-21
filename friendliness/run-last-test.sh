#!/bin/bash

clear
# interactive
./main.py < "$(ls -t ./*.input | head -n1)"

# batch
#./main.py maxsquare-7056x9336-8t.map
