SHELL := /bin/bash


.PHONY: help dependencies remove examples
help:
	@echo "TARGETS: "
	@echo "    install : install pin, maptracer, and mapanalyzer"
	@echo "    remove  : remove pin, maptracer, and mapanalyzer"
	@echo "    help    : print this message"
	@echo "    test    : test the installation of the components"
dependencies:
	sudo dnf install --assumeyes make gcc gcc-c++ wget tar python3 python3-pip
	python3 -m pip install setuptools wheel matplotlib jsonschema colorama
remove:
	$(MAKE) -C mapanalyzer remove
	$(MAKE) -C maptracer remove
	$(MAKE) -C pin remove
examples:
	make -C examples all


.PHONY: install install_pin install_maptracer install_mapanalyzer
install: install_pin install_maptracer install_mapanalyzer
install_pin:
	@echo -e "==================================="
	@echo -e "  INSTALLING PIN"
	@echo -e "==================================="
	$(MAKE) -C pin install
	@echo -e "==================================="
	@echo -e "  TESTING PIN"
	@echo -e "==================================="
	$(MAKE) -C pin test
	@echo -e "\n\n"
install_maptracer:
	@echo -e "==================================="
	@echo -e "  INSTALLING MAPTRACER"
	@echo -e "==================================="
	source /etc/profile.d/pin_env_var.sh && $(MAKE) -C maptracer install
	@echo -e "==================================="
	@echo -e "  TESTING MAPTRACER"
	@echo -e "==================================="
	source /etc/profile.d/pin_env_var.sh && $(MAKE) -C maptracer my_test
	@echo -e "\n\n"
install_mapanalyzer:
	@echo -e "==================================="
	@echo -e "  INSTALLING MAPANALIZER"
	@echo -e "==================================="
	$(MAKE) -C mapanalyzer install
	@echo -e "==================================="
	@echo -e "  TESTING MAPANALIZER"
	@echo -e "==================================="
	$(MAKE) -C mapanalyzer test
	@echo -e "\n"
	@echo -e "\033[33mLOGOUT/LOGIN or REBOOT to finish installation.\033[0m"


.PHONY: publish clean
publish:
	@echo -e "==================================="
	@echo -e "  PRODUCING RESULTS WEBSITE"
	@echo -e "==================================="
	rm -rf public
	mkdir -p public/examples
	cp -r examples/__EXPORT/. public/examples/
	cp examples/index_template.html style.css public/
	python3 examples/fill_template.py public/
	rm public/index_template.html
clean:
	rm -rf public
