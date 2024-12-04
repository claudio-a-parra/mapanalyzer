VERSION := 3.30-98830-g1d7b601b3-gcc-linux
PIN_WEBSITE := https://www.intel.com/content/www/us/en/developer/articles/tool/pin-a-binary-instrumentation-tool-downloads.html
DL_LINK := https://software.intel.com/sites/landingpage/pintool/downloads/pin-$(VERSION).tar.gz
PIN_ENV_FILE := /etc/profile.d/pin_env_var.sh
.PHONY: help install remove quiet-remove download

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

install: quiet-remove ./versions/pin-$(VERSION).tar.gz
	sudo mkdir -p /opt/intel
	sudo tar -xzpf ./versions/pin-$(VERSION).tar.gz -C /opt/intel/
	sudo ln -s /opt/intel/pin-$(VERSION) /opt/intel/pin
	sudo chown -R root:root /opt/intel/pin/
	sudo chmod -R a+rx /opt/intel/pin/
	echo "export PIN_ROOT=/opt/intel/pin" | sudo tee $(PIN_ENV_FILE) >/dev/null
	sudo chmod +x $(PIN_ENV_FILE)
	sudo ln -s /opt/intel/pin/pin /usr/local/bin/pin
	@echo -e "\033[31mRun 'source $(PIN_ENV_FILE)' in your terminal to set the environment variable PIN_ROOT\033[0m"

quiet-remove:
	sudo rm -rf /opt/intel/pin-$(VERSION)
	sudo rm -f /opt/intel/pin
	sudo rm -f /usr/local/bin/pin
	sudo rm -f $(PIN_ENV_FILE)
	sudo rmdir /opt/intel || true

remove: quiet-remove
	@echo -e "\033[31mRun 'unset PIN_ROOT' in your terminal to unset the environment variable PIN_ROOT\033[0m"

download: ./versions/pin-$(VERSION).tar.gz


./versions/pin-$(VERSION).tar.gz:
	@echo "Downloading PIN $(VERSION)"
	wget -P ./versions $(DL_LINK)

test:
	pin -version
