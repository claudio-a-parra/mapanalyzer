all: build run read

wait:
	@sleep 3

build:
	@echo "EXAMPLE: building..."
	gcc -Wall -g -o example example.c -lpthread
	@ echo "EXAMPLE: building OK"

run:
	@sleep 2
	@echo "EXAMPLE: running pin..."
	@if pin -t obj-intel64/mem_tracer.so -- ./example; then \
		echo "EXAMPLE: running pin: OK" ;\
	else \
		echo "EXAMPLE: running pin: FAIL" ;\
		[[ -f pintool.log ]] && bat pintool.log ;\
		[[ -f pin.log ]] && bat pin.log ;\
	fi

read:
	@ clear -x
	@ if [[ -f mem_trace_log.out ]]; then \
		echo "------------ mem_trace_log.out ------------" ;\
		if [[ "$(wc -l mem_trace_log.out)" -lt 37 ]]; then \
			head -n25 mem_trace_log.out ;\
			echo "..." ;\
			tail -n10 mem_trace_log.out ;\
		else \
			cat mem_trace_log.out ;\
		fi ;\
	else \
		echo "EXAMPLE: File 'mem_trace_log.out' not found." ;\
	fi
