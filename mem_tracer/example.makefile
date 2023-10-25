all:
	clear
	make
	gcc -Wall -o example example.c
	pin -t obj-intel64/mem_tracer.so -- ./example
	tail -n+7 mem_trace_log.out > mem_trace_log.csv
	bat mem_trace_log.out
