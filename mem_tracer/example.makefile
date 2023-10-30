all: build run read

wait:
	@sleep 3

build:
	@echo "EXAMPLE: building..."
	gcc -Wall -o example example.c -lpthread
	@ echo "EXAMPLE: building OK"

run:
	@echo "EXAMPLE: running pin..."
	@if pin -t obj-intel64/mem_tracer.so -- ./example; then \
		echo "EXAMPLE: running pin: OK" ;\
	else \
		echo "EXAMPLE: running pin: FAIL" ;\
		[[ -f pintool.log ]] && bat pintool.log ;\
		[[ -f pin.log ]] && bat pin.log ;\
	fi

read:
	@ if [[ -f mem_trace_log.out ]]; then \
		echo "------------ mem_trace_log.out ------------" ;\
		head -n60 mem_trace_log.out ;\
		echo "..." ;\
		tail -n60 mem_trace_log.out ;\
	else \
		echo "EXAMPLE: File 'mem_trace_log.out' not found." ;\
	fi
