MAP=tiny.map

all:
	@clear
	@echo '---- START ---------------------' ;\
	python ../main.py -c tiny_cache.conf $(MAP) ;\
	echo '----- END -----------------------'

view:
	@if [ -f *plot-00* ]; then geeqie *plot-00* & disown; else echo "No plot produced"; fi

watch:
	@find .. -name '*.py' -or -name '*.conf' -or -name '*.map' | entr -p make --no-print-directory all
