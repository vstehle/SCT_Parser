# Simple makefile to generate the documentation with pandoc.
.PHONY: all doc help clean check

all: doc

help:
	@echo 'Targets:'
	@echo '  all'
	@echo '  check   Perform sanity checks'
	@echo '          (currently yamllint, shellcheck, flake8 and mypy,'
	@echo '           as well as configuration and sequence files database'
	@echo '           validation and unit test)'
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
	mypy --strict validate.py
	mypy .
	./validate.py --schema schemas/config-schema.yaml EBBR.yaml
	./validate.py --schema schemas/config-schema.yaml SIE.yaml
	./validate.py --schema schemas/config-schema.yaml sample/sample.yaml
	./validate.py --schema schemas/seq_db-schema.yaml seq_db.yaml
	./tests/test-parser

clean:
	-rm -f README.pdf test-parser.log
