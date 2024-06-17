MAP=tiny.map
prefix=tiny_plot
format=pdf

all:
	@clear
	@echo '---- START ---------------------' ;\
	python ../main.py -c tiny_cache.conf --format $(format) $(MAP) ;\
	echo '----- END -----------------------'

view:
	@( \
		if find . -name '*plot-00*' >/dev/null; then \
			if [[ "$(format)" = "png" ]]; then \
				feh --auto-reload --scale-down *plot-00*.png & disown ;\
			else \
				pdftk $(prefix)-0*.pdf cat output $(prefix).pdf \
					&& rm $(prefix)-0*.pdf \
					&& okular $(prefix).pdf & disown ;\
			fi ;\
		else \
			echo "No plot produced" ;\
		fi ;\
	)

watch:
	@find .. -name '*.py' -or -name '*.conf' -or -name '*.map' | entr -p make --no-print-directory all
