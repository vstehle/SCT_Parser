#!/bin/bash
set -eu

d="${1:-log/}"

find "$d" -name '*.ekl' -exec iconv -f UTF-16 -t UTF-8 {} \; |\
	iconv -f UTF-8 -t UTF-16 > cat_summary.ekl
