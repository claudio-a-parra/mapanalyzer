PYTHON ?= python3
SETUP_FILE = setup.py
PROJECT = mapanalyzer

# Default target
all: install

# Check if Python is installed
check_python:
	@command -v $(PYTHON) >/dev/null 2>&1 || { echo >&2 "Python is not installed. Aborting."; exit 1; }
	@$(PYTHON) -c 'import sys; exit(1) if sys.version_info[0] < 3 else exit(0)' || { echo >&2 "Python 3 is required. Aborting."; exit 1; }

# Install the Python package system-wide
install: check_python
	@echo "Installing package..."
	$(PYTHON) -m pip install --user .

clean:
	rm -rf ./build ./dist ./$(PROJECT).egg-info

# Uninstall the Python package
uninstall: check_python
	@echo "Uninstalling package..."
	$(PYTHON) -m pip uninstall -y $(PROJECT)
