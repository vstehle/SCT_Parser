# EDK2 SCT Results Parser

This is an external parser script for [UEFI SCT]. (WIP)

It's designed to read a `.ekl` results log from an [UEFI SCT] run, and a
generated `.seq` from [UEFI SCT] configurator.

It will proceed to generate a Markdown file listing number of failures, passes, each test from the sequence file set that was Silently dropped, and a list of all failures and warnings.

[UEFI SCT]: https://uefi.org/testtools

## Quick Start

If you're using this tool to analyze EBBR test results, use the following
command. The parsed report can be found in `result.md`.

``` {.sh}
$ ./parser.py --config EBBR.yaml \
		</path/to/sct_results/Overall/Summary.ekl> \
		<path/to/sct_results/Sequence/EBBR.seq>
INFO apply_rules: Updated 200 test(s) out of 12206 after applying 124 rule(s)
INFO main: 0 dropped(s), 1 failure(s), 93 ignored(s), 106 known u-boot limitation(s), 12006 pass(s), 0 warning(s)
```

## Usage
Usage to generate a "result md" is such. `python3 parser.py <log_file.ekl> <seq_file.seq>`
If you do no provided any command line arguments it will use `sample.ekl` and `sample.seq`.
The output filename can be specified with `--md <filename>`.

An online help is available with the `-h` option.

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

## Configuration file

It is possible to use a configuration file with command line option `--config
<filename>`.
This configuration file describes operations to perform on the tests results,
such as marking tests as false positives or waiving failures.

Example command for [EBBR]:

``` {.sh}
$ ./parser.py --config EBBR.yaml /path/to/Summary.ekl EBBR.seq ...
```

You need to install the [PyYAML] module for this to work.

[EBBR]: https://github.com/ARM-software/ebbr
[PyYAML]: https://github.com/yaml/pyyaml

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

A `sample.yaml` configuration file is provided as example, to use with the
`sample.ekl` and `sample.seq` files.

Try it with:

``` {.sh}
$ ./parser.py --config sample.yaml ...
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

The `EBBR.yaml` file is a configuration file meant for [EBBR] testing. It can
override the result of some tests with the following ones:

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
-------------------------------------------------------------------------------

Some of the rules just add a `comments` field with some help text.

## Notes
### Known Issues:
* "comment" is currently not implemented, as formatting is not currently consistent, should reflect the comments from the test.
* some [UEFI SCT] tests have shared GUIDs,
* some lines in ekl file follow Different naming Conventions
* some tests in the sequence file are not strongly Associated with the test spec.

### Documentation

It is possible to convert this `README.md` into `README.pdf` with pandoc using
`make doc`. See `make help`.

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

-------------------------------------------------------------------------------
           Sub-folder  Contents
---------------------  --------------------------------------------------------
 `v21.05_0.8_BETA-0/`  EBBR sequence file from [ACS-IR v21.05_0.8_BETA-0].

   `v21.07_0.9_BETA/`  EBBR sequence files from [ACS-IR v21.07_0.9_BETA].
-------------------------------------------------------------------------------

[ACS-IR v21.05_0.8_BETA-0]: https://github.com/ARM-software/arm-systemready/tree/main/IR/prebuilt_images/v21.05_0.8_BETA-0
[ACS-IR v21.07_0.9_BETA]: https://github.com/ARM-software/arm-systemready/tree/main/IR/prebuilt_images/v21.07_0.9_BETA
