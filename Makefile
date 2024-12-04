SHELL := /bin/bash

.PHONY: help install remove check

help:
	echo "TARGETS: "
	echo "    install : install pin, maptracer, and mapanalyzer"
	echo "    remove  : remove pin, maptracer, and mapanalyzer"
	echo "    help    : print this message"
	echo "    test    : test the installation of the components"

install:
	@echo -e "==================================="
	@echo -e "  PIN"
	@echo -e "==================================="
	$(MAKE) -C pin install
	@echo -e "\n\n==================================="
	@echo -e "  MAPTRACER"
	@echo -e "==================================="
	source /etc/profile.d/pin_env_var.sh && $(MAKE) -C maptracer install
	@echo -e "\n\n==================================="
	@echo -e "  MAPANALIZER"
	@echo -e "==================================="
	$(MAKE) -C mapanalyzer install

remove:
	$(MAKE) -C mapanalyzer remove
	$(MAKE) -C maptracer remove
	$(MAKE) -C pin remove

test:
	$(MAKE) -C pin test
	$(MAKE) -C maptracer my_test
	$(MAKE) -C mapanalyzer test
