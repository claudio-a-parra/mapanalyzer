all: build run read

build:
	make
	gcc -Wall -o example example.c

run:
	pin -t obj-intel64/mem_tracer.so -- ./example || bat pintool.log

read:
	@head -n20 mem_trace_log.out
	@echo "..."
	@tail -n20 mem_trace_log.out
