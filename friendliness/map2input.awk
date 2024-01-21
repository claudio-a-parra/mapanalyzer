#!/bin/gawk -f

# Set field separator to colon or comma
BEGIN {
    FS="[: ,]+"
}

# Process METADATA section
/^# METADATA/ {
    metadata = 1
}

# Process DATA section
/^# DATA/ {
    metadata = 0
}

# Process METADATA lines
metadata == 1 && NF > 0 {
    if ($1 == "start-addr") {
        address = strtonum($2)
    }
}

# Process DATA lines
metadata == 0 && NF > 0 {
    if ($3 == "W" || $3 == "R") {
        result = address + $5
        size = $4
        printf "0x%x,%d\n", result, size
    }
}
END {
    print "exit"
}
