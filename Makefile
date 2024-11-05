

.PHONY: help install remove check

help:
	echo "TARGETS: "
	echo "    install : install pin, maptracer, and mapanalyzer"
	echo "    remove  : remove pin, maptracer, and mapanalyzer"
	echo "    help    : print this message"
	echo "    test    : test the installation of the components"

install:
	$(MAKE) -C pin install
	$(MAKE) -C maptracer install
	$(MAKE) -C mapanalyzer install

remove:
	$(MAKE) -C mapanalyzer remove
	$(MAKE) -C maptracer remove
	$(MAKE) -C pin remove

test:
	$(MAKE) -C pin test
	$(MAKE) -C maptracer my_test
	$(MAKE) -C mapanalyzer test
