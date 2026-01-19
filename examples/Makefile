SHELL := /bin/bash

out_dirs     = maps pdata plots aggr
OUTS         = __EXPORT
all_examples = $(filter-out $(OUTS),$(patsubst ./%/,%,$(wildcard ./*/)))


.PHONY: all $(all_examples)
all: $(all_examples)
$(all_examples):
	@echo -e "\n\033[1mEXAMPLE $@:\033[0m"
	[[ -f "$@/export.sh" ]] || exit 1
	./$@/export.sh
	for outd in $(out_dirs); do \
		compgen -G "$@/$${outd}/*" &>/dev/null || continue; \
		mkdir -p "$(OUTS)/$@/$${outd}"; \
		mv -t "$(OUTS)/$@/$${outd}" "$@/$${outd}"/*; \
		cp "$@/README.md" "$(OUTS)/$@"; \
	done


clean:
	rm -rf $(OUTS) index.html
	for ex in $(all_examples); do \
		$(MAKE) -C "$$ex" clean; \
	done
