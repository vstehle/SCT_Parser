# EDK2 SCT Results Parser

This is an external parser script for [UEFI SCT]. (WIP)

It's designed to read a `.ekl` results log from an [UEFI SCT] run, and a
generated `.seq` from [UEFI SCT] configurator.

It will proceed to generate a Markdown file listing number of failures, passes, each test from the sequence file set that was Silently dropped, and a list of all failures and warnings.

[UEFI SCT]: https://uefi.org/testtools

## Branches

For IR 1.1 certification, git branch `ir1` of this repository should be used.

## Dependencies

You need to install the [PyYAML] module for the configuration file to be loaded
correctly. Depending on your Linux distribution, this might be available as the
`python3-yaml` package.
It is also recommended to install the [packaging] library for smooth version
detection. Depending on your Linux distribution, this might be available as the
`python3-packaging` package.
The [python-jsonschema] module is required for configuration validation.
See [Configuration file].
The [junit-xml] module to allow junit format report generation.

If you want to generate the pdf version of this documentation or convert
markdown results to HTML, you need to install [pandoc]. See [Usage] and
[Documentation].

[PyYAML]: https://github.com/yaml/pyyaml
[packaging]: https://github.com/pypa/packaging
[junit-xml]: https://pypi.org/project/junit-xml
[pandoc]: https://pandoc.org
[python-jsonschema]: https://python-jsonschema.readthedocs.io

## Quick Start

If you're using this tool to analyze EBBR test results, use the following
command. The parsed report can be found in `result.md`.

``` {.sh}
$ ./parser.py \
                </path/to/sct_results/Overall/Summary.ekl> \
		contrib/v21.07_0.9_BETA/EBBR.seq
INFO apply_rules: Updated 200 tests out of 12206 after applying 124 rules
INFO main: 0 dropped, 1 failure, 93 ignored, 106 known u-boot limitations, 12006 pass, 0 warning
```

(The `EBBR.yaml' configuration file is used to process results by default. See
[Configuration file selection].)

## Usage

Usage to generate a `result.md` is such:

``` {.sh}
$ python3 parser.py <log_file.ekl> <seq_file.seq>
```

The output filename can be specified with the `--md` option:

``` {.sh}
$ ./parser.py --md out.md ...
```

To generate a JUnit format report you can specify the output file with the `--junit` option:

``` {.sh}
$ ./parser.py --junit report.xml ...
```

An online help is available with the `-h` option.

The generated `result md` can be easily converted to HTML using [pandoc] with:

``` {.sh}
$ pandoc -oresult.html result.md
```

See [Dependencies].

### Custom search
For a custom Key:value search, the next two arguments *MUST be included together.* The program will search and display files that met that constraint, without the crosscheck, and display the names, guid, and key:value to the command line. `python3 parser.py <file.ekl> <file.seq> <search key> <search value>`

you can use the `test_dict` below to see available keys.

### Sorting data

It is possible to sort the tests data before output using
the `--sort <key1,key2,...>` option.
Sorting the test data helps when comparing results with diff.

Example command:

``` {.sh}
$ ./parser.py --sort \
      'group,descr,set guid,test set,sub set,guid,name,log' ...
```

### Filtering data

The `--filter` option allows to specify a python3 expression, which is used as a
filter. The expression is evaluated for each test; if it evaluates to True the
test is kept, otherwise it is omitted. The expression has access to the test
as dict "x".

Example command, which keeps only the failed tests:

``` {.sh}
$ ./parser.py --filter "x['result'] == 'FAILURE'" ...
```

Filtering takes place after the configuration rules, which are described below.

This filtering mechanism can also be (ab)used to transform tests results.

Example command, which adds a "comment" field (and keeps all the tests):

``` {.sh}
$ ./parser.py \
      --filter "x.update({'comment': 'Transformed'}) or True" ...
```

Example command, which removes filenames prefixes in the "log" field (and keeps
all the tests):

``` {.sh}
$ ./parser.py \
      --filter "x.update({'log': re.sub(r'/.*/', '', x['log'])}) \
                or True" ...
```

### Keeping only certain fields

Except for the markdown and the config template formats, it is possible to
specify which tests data fields to actually write using the `--fields` option.

Example command, suitable for triaging:

``` {.sh}
$ ./parser.py --fields 'result,sub set,descr,name,log' ...
```

The csv format and printing to stdout can retain the fields order.

### Collapsing duplicates

It is possible to "collapse" duplicate tests data into a single entry using the
`--uniq` option, much similar in principle to the UNIX `uniq -c` command.

This step happens after tests and fields filtering, and it adds a "count" field.

Example command, suitable for triaging:

``` {.sh}
$ ./parser.py \
      --filter "x.update({'log': re.sub(r'/.*/', '', x['log'])}) \
                or x['result'] != 'PASS'" \
      --fields 'count,result,sub set,descr,name,log' --uniq ...
```

### Printing a summary

It is possible to print results to stdout using the `--print` option. This is
more useful when only few fields are printed. Example command:

Example printing command:

``` {.sh}
$ ./parser.py --fields 'result,name' --print ...
```

More condensed summaries can be obtained with further filtering.

Example summary command:

``` {.sh}
$ ./parser.py \
      --filter "x.update({'log': re.sub(r'/.*/', '', x['log'])}) \
                or x['result'] in ['FAILURE', 'WARNING']" \
      --fields 'count,result,name' --uniq --print ...
```

### Re-reading markdown results

It is possible to re-read a previously generated markdown results file with the
`--input-md` option. This can be useful to perform further processing on the
tests.

Example command to read a previously generated markdown:

``` {.sh}
$ ./parser.py --input-md 'result.md' ...
```

* By default an output markdown is still generated, except in the case where the
  input and output markdown have the same filename.
* The generated markdown results do not contain the "passed" tests. They can
  therefore not be re-read.

## Configuration file

By default, the `EBBR.yaml` configuration file is used to process results. It is
intended to help triaging failures when testing specifically for [EBBR]
compliance. It describes operations to perform on the tests results,
such as marking tests as false positives or waiving failures.
It is possible to specify another configuration file with the command line
option `--config <filename>`.

You need to install the [PyYAML] module for the configuration file to be loaded
correctly, and installing the [packaging] library is recommended. See
[Dependencies].

[EBBR]: https://github.com/ARM-software/ebbr

### Configuration file selection

The selection of the configuration file is done in the following order:

1. If a command line configuration is specified with the `--config' argument,
   use it.
2. If a sequence file has been identified, use the corresponding configuration
   file specified in the sequence files database.
3. By default, use the `EBBR.yaml` configuration file.

### Configuration file format

The configuration file is in [YAML] format. It contains a list of rules:

``` {.yaml}
- rule: name/description (optional)
  criteria:
    key1: value1
    key2: value2
    ...
  update:
    key3: value3
    key4: value4
    ...
- rule...
```

See also [Validating configurations].

[YAML]: https://yaml.org

### Rule processing

The rules will be applied to each test one by one in the following manner:

* An attempt is made at matching all the keys/values of the rule's 'criteria'
  dict to the keys/values of the test dict. Matching test and criteria is done
  with a "relaxed" comparison (more below).
  - If there is no match, processing moves on to the next rule.
  - If there is a match:
    1. The test dict is updated with the 'update' dict of the rule.
    2. An 'Updated by' key is set in the test dict to the rule name.
    3. Finally, no more rule is applied to that test.

A test value and a criteria value match if the criteria value string is present
anywhere in the test value string.
For example, the test value "abcde" matches the criteria value "cd".

You can use `--debug` to see more details about which rules are applied to the
tests.

### Sample

In the folder `sample`, a `sample.yaml` configuration file is provided as
example, to use with the `sample.ekl` and `sample.seq` files.

Try it with:

``` {.sh}
$ ./parser.py --config sample/sample.yaml sample/sample.ekl sample/sample.seq
```

### Generating a configuration template

To ease the writing of yaml configurations, there is a `--template` option to
generate a configuration "template" from the results of a run:

``` {.sh}
$ ./parser.py --template template.yaml ...
```

This generated configuration can then be further edited manually.

* Tests with result "PASS" are omitted.
* The following tests fields are omitted from the generated rule "criteria":
  "iteration", "start date" and "start time".
* The generated rule "criteria" "log" field is filtered to remove the leading
  path before C filename.

### EBBR configuration

The `EBBR.yaml` file is the configuration file used by default. It is meant for
[EBBR] testing and can override the result of some tests with the following
ones:

-------------------------------------------------------------------------------
                   Result  Description
-------------------------  ----------------------------------------------------
                `IGNORED`  False-positive test failure, not mandated by [EBBR]
                           and too fine-grained to be removed from the
                           `EBBR.seq` sequence file.

`KNOWN U-BOOT LIMITATION`  Genuine bugs, which much ultimately be fixed.
                           We know about them; they are due to U-Boot FAT
                           filesystem implementation limitations and they do
                           not prevent an OS to boot.

   `KNOWN ACS LIMITATION`  Genuine bugs, which are fixed in a more recent
                           version of the ACS or which must ultimately be fixed
                           and which we know about.
-------------------------------------------------------------------------------

Some of the rules just add a `comments` field with some help text.

Example command to see those comments:

``` {.sh}
$ ./parser.py \
      --filter "x['result'] == 'FAILURE'" \
      --fields 'count,result,name,comments' --uniq --print ...
```

### SIE configuration

The `SIE.yaml` file is the configuration file to use when certifiying for the
Security Interface Extension. It is meant for [BBSR] testing and can override
the result of some tests with the following ones:

-------------------------------------------------------------------------------
                 Result  Description
-----------------------  ------------------------------------------------------
              `IGNORED`  False-positive test failure, not mandated by [BBSR]
                         and too fine-grained to be removed from the `BBSR.seq`
                         sequence file.

`KNOWN RPMB LIMITATION`  Genuine limitations, we know about them; they are due
                         to eMMC RPMB limitations and they do not prevent
                         Secure Boot.
-------------------------------------------------------------------------------

[BBSR]: https://developer.arm.com/documentation/den0107/b/?lang=en

### Validating configurations

It is possible to validate the configuration using a schema with:

``` {.sh}
$ ./parser.py --validate-config --schema <schema.yaml> ...
```

If no schema is specified, the default `schemas/config-schema.yaml` is used.

See also [Configuration file format].

## Database of sequence files

The `seq_db.yaml` file contains a list of known sequence files, which allows to
identify the input sequence file.

This database file contains lines describing each known sequence file in turn,
in the following format:

```
sha256 description
```

Everything appearing after a '#' sign is treated as a comment and ignored.

The database filename can be specified with the `--seq-db` option.

### Validating database of sequence files

It is possible to validate the database of sequence files using a schema with:

``` {.sh}
$ ./parser.py --validate-seq-db --schema <schema.yaml> ...
```

If no schema is specified, the default `schemas/seq_db-schema.yaml` is used.

## Notes
### Known Issues:
* "comment" is currently not implemented, as formatting is not currently consistent, should reflect the comments from the test.
* some [UEFI SCT] tests have shared GUIDs,
* some lines in ekl file follow Different naming Conventions
* some tests in the sequence file are not strongly Associated with the test spec.

### Documentation

It is possible to convert this `README.md` into `README.pdf` with [pandoc] using
`make doc`. See `make help` and [Dependencies].

### Sanity checks

To perform sanity checks, run `make check`. It runs a number of checkers and
reports errors:

-------------------------------
      Checker  Target
-------------  ----------------
     `flake8`  Python scripts.
   `yamllint`  [YAML] files.
 `shellcheck`  Shell scripts.
-------------------------------

This will also perform validation of the `EBBR.yaml' configuration.
See `make help`.

### db structure:

``` {.python}
tests = [
    test_dict,
    est_dict2...
]

test_dict = {
   "name": "some test",
   "result": "pass/fail",
   "group": "some group",
   "test set": "some set",
   "sub set": "some subset",
   "set guid": "XXXXXX",
   "guid": "XXXXXX",
   "comment": "some comment",
   "log": "full log output"
}


seqs = {
    <guid> : seq_dict
    <guid2> : seq_dict2...
}

seq_dict = {
                "name": "set name",
                "guid": "set guid",
                "Iteration": "some hex/num of how many times to run",
                "rev": "some hex/numb",
                "Order": "some hex/num"
}
```

#### Spurious tests

Spurious tests are tests, which were run according to the log file but were not
meant to be run according to the sequence file.

We force the "result" fields of those tests to "SPURIOUS".

#### Dropped tests sets

Dropped tests sets are the tests sets, which were were meant to be run according
to the sequence file but for which no test have been run according to the log
file.

We create artificial tests entries for those dropped tests sets, with the
"result" fields set to "DROPPED". We convert some fields coming from the
sequence file, and auto-generate others:

``` {.python}
dropped_test_dict = {
   "name": "",
   "result": "DROPPED",
   "group": "Unknown",
   "test set": "",
   "sub set": <name from sequence file>,
   "set guid": <guid from sequence file>,
   "revision": <rev from sequence file>,
   "guid": "",
   "log": ""
}
```

#### Skipped tests sets

Skipped tests sets are the tests sets, which were considered but had zero of
their test run according to the log file.

We create artificial tests entries for those dropped tests sets, with the
"result" fields set to "SKIPPED".

## Contributed files

A few contributed files are stored in sub-folders under `contrib` for
convenience:

--------------------  ---------------------------------------------------------
          Sub-folder  Contents
--------------------  ---------------------------------------------------------
`v21.05_0.8_BETA-0/`  EBBR sequence file from [ACS-IR v21.05_0.8_BETA-0].

  `v21.07_0.9_BETA/`  EBBR sequence files from [ACS-IR v21.07_0.9_BETA].

       `v21.09_1.0/`  EBBR sequence files from [ACS-IR v21.09_1.0].

`v21.10_SIE_REL1.0/`  BBSR sequence file from
                      [Security interface extension ACS v21.10_SIE_REL1.0].
--------------------  ---------------------------------------------------------

[ACS-IR v21.05_0.8_BETA-0]: https://github.com/ARM-software/arm-systemready/tree/main/IR/prebuilt_images/v21.05_0.8_BETA-0
[ACS-IR v21.07_0.9_BETA]: https://github.com/ARM-software/arm-systemready/tree/main/IR/prebuilt_images/v21.07_0.9_BETA
[ACS-IR v21.09_1.0]: https://github.com/ARM-software/arm-systemready/tree/main/IR/prebuilt_images/v21.09_1.0
[Security interface extension ACS v21.10_SIE_REL1.0]: https://github.com/ARM-software/arm-systemready/tree/security-interface-extension-acs/security-interface-extension/prebuilt_images/v21.10_SIE_REL1.0
