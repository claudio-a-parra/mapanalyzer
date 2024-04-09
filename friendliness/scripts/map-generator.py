#!/usr/bin/env python3
import random
def access(i,offset):
    print(f'{i},0,R,8,{offset}')
    return

line_size_bytes = 16
associativity = 2
cache_size_bytes = 256

base_addr = (64+16)
num_sets = cache_size_bytes // (line_size_bytes*associativity)
turn_around = num_sets * line_size_bytes
reads_per_line = 8
cache_read_offsets = [8*x for x in range(reads_per_line)]

times = 2
unique_reads = 64
total_reads = 100

read_number = 0
time_done = False
max_addr = 0
access_list=[]

for i in range(total_reads):
    addr = i*8
    if addr > max_addr:
        max_addr = addr
    access_list.append((i,addr))

"""
for t in range(times):
    for r in range(reads_per_line):
        for s in range(num_sets):
            if read_number == (t+1)*unique_reads:
                time_done = True
                break
            addr = s*turn_around+cache_read_offsets[r]
            if addr > max_addr:
                max_addr = addr
            access_list.append((read_number, addr))
            read_number += 1

        if time_done:
            time_done = False
            break
"""
block_size = max_addr + 8



header=("# METADATA\n"
f"start-addr   : {hex(base_addr)}\n"
f"end-addr     : {hex(base_addr+block_size)}\n"
f"block-size   : {block_size}\n"
"owner-thread : 0\n"
"slice-size   : 500\n"
"thread-count : 1\n"
f"event-count  : {total_reads}\n"
f"max-qtime    : {total_reads - 1}\n"
"\n"
"# DATA\n"
"time,thread,event,size,offset")

print(header)

for acc in access_list:
    access(acc[0], acc[1])


#print('new rep')

# for i,offset in enumerate(offsets):
#     for s in range(reads_per_set):
#         access(i*reads_per_set+s,s*tag_page)



