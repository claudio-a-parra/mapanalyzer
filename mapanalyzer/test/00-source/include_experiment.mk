# binary arguments
algorithm ?= EXAMPLE_ALGORITHM
source ?= main.c
#ccopts = -g -Og -Wall
ccopts ?= -Wall
cclibs ?=
binary ?= $(algorithm)
binary_args ?= EXAMPLE_ARGUMENTS

# access pattern filename
access_pattern ?= $(algorithm)-VARIANT_EXAMPLE.map

# mapanalyzer options
MPL_PW ?= 5
MPL_PH ?= 3.5
MPL_DPI ?= 300
MPL_MRES ?= auto
MPL_FMT ?= pdf
MPL_CACHE ?= ./cache.conf
# include all plots
MPL_PLOTS ?= all
# orientation of X tick labels
MPL_XTORI ?= v
# range for X and Y axes
MPL_XRANGES ?= full
MPL_YRANGES ?= full

EXPORT_DIR ?= __EXPORT
DIAG_ODGs ?= $(wildcard *.odg)
DIAG_PDFs ?= $(patsubst %.odg,diagram-%.pdf,$(DIAG_ODGs))

define HELP_ABOUT
    What is this experiment about.
endef
export HELP_ABOUT
define HELP_USAGE
    make [VARIABLE=VALUE] TARGET
endef
export HELP_USAGE
export HELP_VARIABLES =
define HELP_VARIABLES_COMMON
    MAPANALYZER OPTIONS:
        MPL_PW     : ($(MPL_PW)) Width of the plots.
        MPL_PH     : ($(MPL_PH)) Height of the plots.
        MPL_DPI    : ($(MPL_DPI)) Choose the DPI of the resulting plots.
        MPL_MRES   : ($(MPL_MRES)) Choose the maximum resolution of the MAP.
        MPL_FMT    : ($(MPL_FMT)) Choose the output format of the plots {png, pdf}.
        MPL_CACHE  : ($(MPL_CACHE)) File describing the cache to utilize.
        MPL_PLOTS  : ($(MPL_PLOTS)) Plots to export:
                       all, M:MAP, Ls:SLD, Lt:TLD, I:CMR, C:CMMA, U:CUR, A:AD, S:SIU.
        MPL_XTORI  : ($(MPL_XTORI)) Orientation of X-axis tick labels {v,h}.
        MPL_XRANGES: ($(MPL_XRANGES)) Manual ranges for X-axis:
                       plotcode:min:max
        MPL_YRANGES: ($(MPL_YRANGES)) Manual ranges for Y-axis:
                       plotcode:min:max
        See 'mapanalyzer --help' for more details.
endef
export HELP_VARIABLES_COMMON
define HELP_TARGETS
    help    : print this message.
    all     : build and run the binary, get the map, and plot the thing.
    bin     : build the binary '$(binary)'.
    map     : run the binary and obtain the memory access pattern file.
    plot    : plot the memory access pattern file './$(access_pattern)'.
    diagram : convert ODG diagram into PDF.
    clean   : delete generated plots, map, diagrams, and $(EXPORT_DIR)
    view    : open plots in feh or okular.
    export  : run the script 'export.sh' to generate the desired files
            in directory '$(EXPORT_DIR)'
    endef
export HELP_TARGETS

SHELL ?= /bin/bash

.PHONY: help all export bin map plot diag clean view

help:
	@[[ -n "$$HELP_ABOUT" ]] && echo -e "ABOUT\n$$HELP_ABOUT\n" || true
	@[[ -n "$$HELP_USAGE" ]] && echo -e "USAGE\n$$HELP_USAGE\n" || true
	@echo -e "VARIABLES (default value)"
	@[[ -n "$$HELP_VARIABLES" ]] && echo -e "$$HELP_VARIABLES" || true
	@echo -e "$$HELP_VARIABLES_COMMON\n"
	@echo -e "TARGETS\n$$HELP_TARGETS"

all: bin map plot

export: __EXPORT

$(EXPORT_DIR):
	@echo -e "\033[34m./export.sh\033[0m"
	@MAKEFLAGS="--no-print-directory" ./export.sh

.SUFIXES: # do not build files implicitly

bin: $(binary)

$(binary): $(source)
	@echo -e "\033[34mclang $(ccopts) -o $(binary) $(source) $(cclibs)\033[0m"
	@clang $(ccopts) -o $(binary) $(source) $(cclibs)
#	regenerate local gitignore with the binary's name
	@echo -e '$(binary)\n.gitignore\n$(EXPORT_DIR)/\n' > .gitignore

map: $(access_pattern)

$(access_pattern): $(binary)
	@echo -e "\033[34mpin -t /usr/local/lib/libmaptracer.so -o ./$(access_pattern) -- ./$(binary) $(binary_args)\033[0m"
	@pin -t /usr/local/lib/libmaptracer.so -o ./$(access_pattern) -- ./$(binary) $(binary_args) || echo "Error: Pin returned $$?"
	@[[ -f ./$(access_pattern) ]] || exit 1
	@echo -n $(access_pattern)
	@echo ' ('$$(numfmt --to=iec --suffix=B $$(stat -c %s ./$(access_pattern)))')'
	@if [[ "$$(cat $(access_pattern) | wc -l)" -gt 21 ]]; then \
		(head -n15 ./$(access_pattern) && echo '...' && tail -n5 ./$(access_pattern)) ;\
	else \
		cat ./$(access_pattern) ;\
	fi | awk '/^#/{print "    " $$0} !/^#/ && NF {print "    " $$0}'
	@echo

plot: $(access_pattern)
	@echo -e "\033[34mmapanalyzer --cache $(MPL_CACHE) --plots "$(MPL_PLOTS)" --x-ranges "$(MPL_XRANGES)" --y-ranges "$(MPL_YRANGES)" --x-tick-ori $(MPL_XTORI) --plot-width $(MPL_PW) --plot-height $(MPL_PH) --dpi $(MPL_DPI) --max-res $(MPL_MRES) --format $(MPL_FMT) -- "./$(access_pattern)"\033[0m"
	@mapanalyzer --cache $(MPL_CACHE) --plots "$(MPL_PLOTS)" --x-ranges "$(MPL_XRANGES)" --y-ranges "$(MPL_YRANGES)" --x-tick-ori $(MPL_XTORI) --plot-width $(MPL_PW) --plot-height $(MPL_PH) --dpi $(MPL_DPI) --max-res $(MPL_MRES) --format $(MPL_FMT) -- "./$(access_pattern)"

diagram: $(DIAG_PDFs)

diagram-%.pdf: %.odg
	@echo "libreoffice --headless --convert-to pdf $<"
	@libreoffice --headless --convert-to pdf $< | sed 's|'$$(realpath $$(pwd))'|.|g' >/dev/null
	pdfcrop --noverbose --pdftex $*.pdf $@ >/dev/null
	echo "$@" > .gitignore
	rm -f $*.pdf

clean:
	rm -rf ./__EXPORT
	rm -f $(binary) *_plot-*.{pdf,png} *.map
	rm -f diagram-*.pdf

view:
	@PNGs=$$(find -type f -name '*.png' | sort) ;\
	PDFs=$$(find -type f -name '*.pdf' ! -name '__all_pdf_plots__.pdf' | sort) ;\
	if [[ -n "$$PNGs" ]]; then \
		feh -B "#aaa" --auto-zoom --scale-down --auto-reload --on-last-slide hold $$PNGs & disown ;\
	elif [[ -n "$$PDFs" ]]; then \
		pdftk $${PDFs} cat output ./__all_pdf_plots__.pdf ;\
		(okular ./__all_pdf_plots__.pdf && rm -f ./__all_pdf_plots__.pdf) & disown ;\
	else \
		echo "No plots to view." ;\
	fi
