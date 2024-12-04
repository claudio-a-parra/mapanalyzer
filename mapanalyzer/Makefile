PYTHON ?= python3
SETUP_FILE = setup.py
PROJECT = mapanalyzer

SHELL := /bin/bash

help:
	@echo "TARGETS:"
	@echo "    install : install $(PROJECT) in the system."
	@echo "    remove  : uninstall $(PROJECT) from the system."
	@echo "    test    : test whether $(PROJECT) was correctly installed."
	@echo "    clean   : remove temporary files created during the installation."

check_python:
	@command -v $(PYTHON) >/dev/null 2>&1 || { echo >&2 "Python is not installed. Aborting."; exit 1; }
	@$(PYTHON) -c 'import sys; exit(1) if sys.version_info[0] < 3 else exit(0)' || { echo >&2 "Python 3 is required. Aborting."; exit 1; }
	python3 -m pip --version || python3 -m ensurepip --upgrade

install: check_python
	@echo "Installing package..."
	$(PYTHON) -m pip install --user .

remove: check_python
	@echo "Uninstalling package..."
	$(PYTHON) -m pip uninstall -y $(PROJECT)

clean:
	rm -rf ./build ./dist ./$(PROJECT).egg-info

test:
	mapanalyzer --help
