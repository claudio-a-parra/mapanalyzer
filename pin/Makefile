#VERSION := 3.30-98830-g1d7b601b3-gcc-linux
VERSION := external-4.0-99633-g5ca9893f2-gcc-linux
PIN_WEBSITE := https://www.intel.com/content/www/us/en/developer/articles/tool/pin-a-binary-instrumentation-tool-downloads.html
DL_LINK := https://software.intel.com/sites/landingpage/pintool/downloads/pin-$(VERSION).tar.gz
PIN_ENV_FILE := /etc/profile.d/pin_env_var.sh

SHELL := /bin/bash

.PHONY: help install remove quiet-remove download

help:
	@echo "TARGETS:"
	@echo "    download: download pin-$(VERSION).tar.gz from intel.com."
	@echo "    install : download and install pin in the system."
	@echo "    remove  : remove pin from the system."
	@echo "    help    : print this beautiful message."
	@echo "    test    : run 'pin -version'."
	@echo ""
	@echo "VARIABLES:"
	@echo "    VERSION : ($(VERSION)) Pin version to install."

install: quiet-remove ./versions/pin-$(VERSION).tar.gz
	sudo mkdir -p /opt/intel
	sudo tar -xzpf ./versions/pin-$(VERSION).tar.gz -C /opt/intel/
	sudo ln -s /opt/intel/pin-$(VERSION) /opt/intel/pin
	sudo chown -R root:root /opt/intel/pin/
	sudo chmod -R a+rx /opt/intel/pin/
	echo "export PIN_ROOT=/opt/intel/pin" | sudo tee $(PIN_ENV_FILE) >/dev/null
	sudo chmod +x $(PIN_ENV_FILE)
	sudo ln -s /opt/intel/pin/pin /usr/local/bin/pin
	@echo -e "\033[33mRun 'source $(PIN_ENV_FILE)' in your terminal to set the environment variable PIN_ROOT\033[0m"

quiet-remove:
	sudo rm -rf /opt/intel/pin-$(VERSION)
	sudo rm -f /opt/intel/pin
	sudo rm -f /usr/local/bin/pin
	sudo rm -f $(PIN_ENV_FILE)
	# if /opt/intel is empty, remove it too
	sudo rmdir /opt/intel 2>/dev/null || true

remove: quiet-remove
	@echo -e "\033[33mRun 'unset PIN_ROOT' in your terminal to unset the environment variable PIN_ROOT\033[0m"

download: ./versions/pin-$(VERSION).tar.gz


./versions/pin-$(VERSION).tar.gz:
	@echo "Downloading PIN $(VERSION)"
	@if ! wget -P ./versions $(DL_LINK); then \
		echo "Error downloading pin from $(DL_LINK)" ;\
		echo "Download it manually and put it in ./versions/pin-$(VERSION).tar.gz" ;\
		echo "Then run 'make install'" ;\
		exit 1 ;\
	fi

test:
	pin -version
