name     := $(shell basename $$PWD)
LS       := 6
RS       := 0
source   := main.c
binary   := $(name)
bin_args := $(LS) $(RS)

CC       := gcc
CCOPTS   := -Wall -O0 -g
CCLIBS   :=
lmt_path := /usr/local/lib/libmaptracer.so 

dir_map  := maps
dir_pdata:= pdata
dir_plot := plots
dir_aggr := aggr

timestamp:= $(shell date +%Y%m%d_%H%M%S)
map_file := $(name)_$(timestamp).map
pin_num_threads := 1



.PHONY: help all clean mkdirs
help:
	echo "TARGETS"
	echo "  - build: build the $(name) binary '$(binary)'"
	echo "  - run  : simply run './$(binary) $(bin_args)'. Nothing special."
	echo "  - map  : run $(binary), but this time capturing its MAP into './$(dir_map)/$(name)_TIMESTAMP.map'"
	echo "  - plot : Plot a captured MAP"
all: map plot
mkdirs:
	@mkdir -p ./$(dir_map) ./$(dir_pdata) ./$(dir_plot)
clean:
	rm -rf $(binary) $(dir_map) $(dir_pdata) $(dir_plot) $(dir_aggr)


# BUILD
build: $(binary)
$(binary): $(source)
	$(CC) $(CCOPTS) -o $(binary) $(source) $(CCLIBS)


# RUN
run: $(binary)
	./$(binary) $(bin_args)


# MAP
map: ./$(dir_map)/$(map_file)
	@echo $< '('$$(numfmt --to=iec --suffix=B $$(stat -c %s $<))')'
	@if [[ "$$(cat $< | wc -l)" -gt 21 ]]; then \
		(head -n15 $< && echo '...' && tail -n5 $<) ;\
	else \
		cat $< ;\
	fi | awk '/^#/{print "    " $$0} !/^#/ && NF {print "    " $$0}'; echo

./$(dir_map)/$(map_file): $(binary) | mkdirs
	pin -t $(lmt_path) -o $@ -thr $(pin_num_threads) -- ./$(binary) $(bin_args)
	@if [[ ! -f $@ ]]; \
		then echo "Pin did not create a MAP file."; exit 1; \
	fi


# PLOT
# mapanalyzer options
MA_CACHE   = cache.conf
MA_WIDTH   = 5
MA_HEIGHT  = 3.5
MA_DPI     = 600
MA_MAXRES  = auto
MA_METRICS = MAP
MA_BGMET   = MAP
MA_XRANGES = full
MA_YRANGES = full
MA_XORIENT = v
MA_SMRITHR = all
MA_TBOXOFF = default
MA_PLSIZES = default
MA_FORMAT  = pdf
# MA_FLAGS = -Lx -Is
MA_FLAGS = -Is

plot: mkdirs
	@if ! find ./$(dir_map) -maxdepth 1 -type f -name '*.map' -print -quit | grep -q .; then \
		echo "No MAP found, running make again"; \
		make --no-print-directory timestamp=$(timestamp) map; \
	fi
	mapanalyzer \
		--mode sim-plot \
		--cache $(MA_CACHE) \
		--max-res $(MA_MAXRES) \
		--metrics "$(MA_METRICS)" \
		--background-metric $(MA_BGMET) \
		--plot-width $(MA_WIDTH) \
		--plot-height $(MA_HEIGHT) \
		--dpi $(MA_DPI) \
		--x-ranges "$(MA_XRANGES)" \
		--y-ranges "$(MA_YRANGES)" \
		--x-tick-ori $(MA_XORIENT) \
		--short-roundtrip-threshold $(MA_SMRITHR) \
		--textbox-offsets "$(MA_TBOXOFF)" \
		--plots-sizes "$(MA_PLSIZES)" \
		--format $(MA_FORMAT) $(MA_FLAGS) \
		-- ./$(dir_map)/$(map_file)
	mv *.json ./$(dir_pdata)
	mv *.$(MA_FORMAT) ./$(dir_plot)


# AGGREGATE
aggregate: mkdirs
ifeq ($(wildcard ./$(dir_pdata)/$(name)*.json),)
	@echo 'No files ./$(dir_pdata)/$(name)*.json; Nothing to aggregate.'
else
	mapanalyzer \
		--mode aggregate \
		--plot-width $(MA_WIDTH) \
		--plot-height $(MA_HEIGHT) \
		--dpi $(MA_DPI) \
		--x-ranges "$(MA_XRANGES)" \
		--y-ranges "$(MA_YRANGES)" \
		--x-tick-ori $(MA_XORIENT) \
		--short-roundtrip-threshold $(MA_SMRITHR) \
		--textbox-offsets "$(MA_TBOXOFF)" \
		--plots-sizes "$(MA_PLSIZES)" \
		--format $(MA_FORMAT) $(MA_FLAGS) \
		-- ./$(dir_pdata)/$(name)*.json
	mv *.$(MA_FORMAT) ./$(dir_aggr)
endif
