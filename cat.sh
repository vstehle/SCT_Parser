#!/bin/bash

find log/ -name '*.ekl' -exec cat {} \; > cat_summary.ekl
