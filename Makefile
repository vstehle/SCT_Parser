# Simple makefile to generate the documentation with pandoc.
.PHONY: all doc help clean check

all: doc

help:
	@echo 'Targets:'
	@echo '  all'
	@echo '  check   Perform sanity checks'
	@echo '          (currently yamllint, shellcheck and flake8,'
	@echo '           as well as configuration and sequence files database'
	@echo '           validation)'
	@echo '  clean'
	@echo '  doc     Generate README.pdf'
	@echo '  help    Print this help.'

doc: README.pdf

%.pdf: %.md pandoc.yaml
	pandoc -o$@ $< pandoc.yaml

check:
	yamllint .
	shellcheck $$(find -name '*.sh')
	flake8
	./parser.py --validate-config --config EBBR.yaml --schema schemas/config-schema.yaml
	./parser.py --validate-config --config SIE.yaml --schema schemas/config-schema.yaml
	./parser.py --validate-config --config sample/sample.yaml --schema schemas/config-schema.yaml
	./parser.py --validate-seq-db --schema schemas/seq_db-schema.yaml

clean:
	-rm -f README.pdf
