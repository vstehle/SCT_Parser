# Simple makefile to generate the documentation with pandoc.
.PHONY: all doc help clean check

all: doc

help:
	@echo 'Targets:'
	@echo '  all'
	@echo '  check   Perform sanity checks'
	@echo '          (currently yamllint, shellcheck, flake8, mypy and'
	@echo '           pylint, as well as configuration and sequence files'
	@echo '           database validation and unit test)'
	@echo '  clean'
	@echo '  doc     Generate README.pdf'
	@echo '  help    Print this help.'

doc: README.pdf

%.pdf: %.md pandoc.yaml
	pandoc -o$@ $< pandoc.yaml

check:
	yamllint .
	shellcheck $$(find -name '*.sh') tests/test-parser
	flake8
	mypy .
	pylint --rcfile .pylint.rc *.py
	./validate.py --schema schemas/config-schema.yaml EBBR.yaml
	./validate.py --schema schemas/config-schema.yaml SIE.yaml
	./validate.py --schema schemas/config-schema.yaml sample/sample.yaml
	./validate.py --schema schemas/seq_db-schema.yaml seq_db.yaml
	./tests/test-parser

clean:
	-rm -f README.pdf test-parser.log
