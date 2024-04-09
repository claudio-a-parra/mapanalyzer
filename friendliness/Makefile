
OPTS = -w 100
MAPS = $(wildcard map-samples/*.map)

.PHONY: all clean

all:
	@( \
	for m in $(MAPS); do \
		echo -e "\n---  $$m  ------------------------------------"; \
		./scripts/main.py $(OPTS) "$$m"; \
	done; )

clean:
	rm -f *.png
