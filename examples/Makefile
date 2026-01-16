SHELL := /bin/bash

all_examples := $(patsubst ./%/,%,$(wildcard ./*/))
out_dirs     := maps pdata plots aggr
OUTS         := __EXPORT

.PHONY: all
all:
	@for ex in $(all_examples); do \
		echo -e "\nEXAMPLE $${ex^^}:"; \
		$(MAKE) -C "$$ex" all; \
		for outd in $(out_dirs); do \
			if find "$${ex}/$${outd}" -type f -print -quit 2>/dev/null | grep -q .; then \
				mkdir -p "$(OUTS)/$${ex}"; \
				mv -t "$(OUTS)/$${ex}" "$${ex}/$${outd}"; \
			fi; \
		done; \
	done

clean:
	rm -rf $(OUTS)
	@for ex in $(all_examples); do \
		$(MAKE) -C "$$ex" clean; \
	done
