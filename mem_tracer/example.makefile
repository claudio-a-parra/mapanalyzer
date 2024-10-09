NAME = "EXAMPLE: "
PIN_LOG = mem_access_pattern.map

all: build run read

build:
	@echo "$(NAME)building ---------------------"
	clang -Wall -g -o example example.c -lpthread
	@echo -e "---------------------------------------\n"

run:
	@sleep 2
	@echo "$(NAME)running pin ------------------"
	@if ! pin -t obj-intel64/mem_tracer.so -- ./example; then \
		echo "EXAMPLE: running pin: FAIL!" ;\
		[[ -f pintool.log ]] && bat pintool.log ;\
		[[ -f pin.log ]] && bat pin.log ;\
	fi ;\
	echo -e "---------------------------------------\n" ;\

read:
	@ if [[ -f $(PIN_LOG) ]]; then \
		echo "$(NAME)$(PIN_LOG) -------" ;\
		if [[ "$(wc -l $(PIN_LOG))" -lt 37 ]]; then \
			head -n25 $(PIN_LOG) ;\
			echo "..." ;\
			tail -n10 $(PIN_LOG) ;\
		else \
			cat $(PIN_LOG) ;\
		fi ;\
	else \
		echo "$(NAME)File '$(PIN_LOG)' not found." ;\
	fi ;\
	echo -e "---------------------------------------\n" ;\
