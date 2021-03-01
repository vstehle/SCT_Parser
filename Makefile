# Simple makefile to generate the documentation with pandoc.
.PHONY: all doc help clean

all: doc

help:
	@echo 'Targets:'
	@echo '  all'
	@echo '  clean'
	@echo '  doc     Generate README.pdf'
	@echo '  help    Print this help.'

doc: README.pdf

%.pdf: %.md pandoc.yaml
	pandoc -o$@ $< pandoc.yaml

clean:
	-rm -f README.pdf
