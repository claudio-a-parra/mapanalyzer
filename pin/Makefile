VERSION := 3.30-98830-g1d7b601b3-gcc-linux
PIN_WEBSITE := https://www.intel.com/content/www/us/en/developer/articles/tool/pin-a-binary-instrumentation-tool-downloads.html
DL_LINK := https://software.intel.com/sites/landingpage/pintool/downloads/pin-$(VERSION).tar.gz

.PHONY: help install remove

help:
	@echo "DOWNLOAD PIN:"
	@echo "    Make sure of getting the version that this makefile point to ($(VERSION))."
	@echo "    You should be able to get it from:"
	@echo "      $(DL_LINK)"
	@echo "    Otherwise, you can browse a version in:"
	@echo "      $(PIN_WEBSITE)"
	@echo "    Once downloaded, put the tar.gz file in the directory './versions/', then run 'make install'"
	@echo ""
	@echo "TARGETS:"
	@echo "    install : install pin in the system"
	@echo "    remove  : remove pin from the system"
	@echo "    help    : print this beautiful message"
	@eoch "    test    : run 'pin -version'"
	@echo ""
	@echo "VARIABLES:"
	@echo "    VERSION : ($(VERSION)) Pin version to install."

install: remove
	@if [[ ! -f ./versions/pin-$(VERSION).tar.gz ]]; then \
		echo "Error: file './versions/pin-$(VERSION).tar.gz' does not exist." >&2 ;\
		exit 1 ;\
	fi
	sudo mkdir -p /opt/intel
	sudo tar -xzpf ./versions/pin-$(VERSION).tar.gz -C /opt/intel/
	sudo ln -s /opt/intel/pin-$(VERSION) /opt/intel/pin
	sudo chown -R root:root /opt/intel/pin/
	sudo chmod -R a+rx /opt/intel/pin/
	export PIN_ROOT=/opt/intel/pin
	sudo ln -s /opt/intel/pin/pin /usr/local/bin/pin

remove:
	sudo rm -rf /opt/intel/pin-$(VERSION)
	sudo rm -f /opt/intel/pin
	sudo rm -f /usr/local/bin/pin
	sudo rmdir /opt/intel || true

test:
	pin -version
