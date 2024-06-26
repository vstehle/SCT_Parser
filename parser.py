#!/usr/bin/env python3
# SCT log parser


import sys
import argparse
import csv
import logging
import json
import re
import hashlib
import os
import curses
import time
import subprocess
from typing import Any, IO, Optional, cast, TypedDict, Callable
import yaml

try:
    from packaging import version
except ImportError:
    print('No packaging. You should install python3-packaging...')

try:
    from junit_xml import TestSuite, TestCase
except ImportError:
    print(
        'No junit_xml. You should install junit_xml for junit output'
        ' support...')

Dumper: Any

try:
    from yaml import CDumper as Dumper
except ImportError:
    from yaml import Dumper

DbEntry = dict[str, str]
DbType = list[DbEntry]


class ConfigEntry(TypedDict):
    rule: str
    criteria: DbEntry
    update: DbEntry


ConfigType = list[ConfigEntry]
MetaData = dict[str, str]


class SeqFile(TypedDict):
    sha256: str
    name: str
    config: str


class SeqDb(TypedDict):
    seq_db: None
    seq_files: list[SeqFile]


BinsType = dict[str, list[dict[str, str]]]

# Not all yaml versions have a Loader argument.
if 'packaging.version' in sys.modules and \
   version.parse(yaml.__version__) >= version.parse('5.1'):
    yaml_load_args = {'Loader': yaml.FullLoader}
else:
    yaml_load_args = {}

# Colors
normal = ''
red = ''
yellow = ''
green = ''

if os.isatty(sys.stdout.fileno()):
    try:
        curses.setupterm()
        setafb = curses.tigetstr('setaf') or bytes()
        setaf = setafb.decode()
        tmp = curses.tigetstr('sgr0')
        normal = tmp.decode() if tmp is not None else ''
        red = curses.tparm(setafb, curses.COLOR_RED).decode() or ''
        yellow = curses.tparm(setafb, curses.COLOR_YELLOW).decode() or ''
        green = curses.tparm(setafb, curses.COLOR_GREEN).decode() or ''
    except Exception:
        pass


# Compute the plural of a word.
def maybe_plural(n: int, word: str) -> str:
    if n < 2:
        return word

    ll = word[len(word) - 1].lower()

    if ll in ('d', 's'):
        return word

    return f'{word}s'


# based loosley on https://stackoverflow.com/a/4391978
# returns a filtered list of dicts that meet some Key-value pair.
# I.E. key="result" value="FAILURE"
def key_value_find(
        list_1: list[dict[str, str]], key: str, value: str
        ) -> list[dict[str, str]]:

    found = []
    for test in list_1:
        if test[key] == value:
            found.append(test)
    return found


# Were we intrept test logs into test dicts
def test_parser(string: list[str], current: dict[str, str]) -> dict[str, str]:
    test_list = {
        "name": string[2],
        # FIXME:Sometimes, SCT has name and Description,
        "result": string[1],
        **current,
        "guid": string[0],
        # FIXME:GUID's overlap
        # "comment": string[-1], # FIXME:need to hash this out,
        # sometime there is no comments
        "log": ' '.join(string[3:])
    }
    return test_list


# Parse the ekl file, and create a map of the tests
def ekl_parser(file: list[str]) -> list[dict[str, str]]:
    # create our "database" dict
    temp_list = []
    # All tests are grouped by the "HEAD" line, which precedes them.
    current: dict[str, str] = {}

    # Count number of tests since beginning of the set
    n = 0

    # Number of skipped tests sets
    s = 0

    for i, line in enumerate(file):
        # Strip the line from trailing whitespaces
        line = line.rstrip()

        # Skip empty line
        if line == '':
            continue

        # strip the line of | & || used for sepration
        split_line = line.split('|')

        # TERM marks the end of a test set
        # In case of empty test set we generate an artificial skipped test
        # entry. Then reset current as a precaution, as well as our test
        # counter.
        if split_line[0] == '' and split_line[1] == "TERM":
            if not n:
                logging.debug(f"Skipped test set `{current['sub set']}'")

                temp_list.append({
                    **current,
                    'name': '',
                    'guid': '',
                    'log': '',
                    'result': 'SKIPPED',
                })

                s += 1

            current = {}
            n = 0
            continue

        # The "HEAD" tag is the only indcation we are on a new test set
        if split_line[0] == '' and split_line[1] == "HEAD":
            # split the header into test group and test set.
            try:
                group, Set = split_line[12].split('\\')
            except Exception:
                group, Set = '', split_line[12]
            current = {
                'group': group,
                'test set': Set,
                'sub set': split_line[10],
                'set guid': split_line[8],
                'iteration': split_line[4],
                'start date': split_line[6],
                'start time': split_line[7],
                'revision': split_line[9],
                'descr': split_line[11],
                'device path': '|'.join(split_line[13:]),
            }

        # FIXME:? EKL file has an inconsistent line structure,
        # sometime we see a line that consits ' dump of GOP->I\n'
        # easiest way to skip is check for blank space in the first char
        elif split_line[0] != '' and split_line[0][0] != " ":
            try:
                # deliminiate on ':' for tests
                split_test = [new_string for old_string in
                              split_line for new_string in
                              old_string.split(':')]
                # put the test into a dict, and then place that dict in another
                # dict with GUID as key
                tmp_dict = test_parser(split_test, current)
                temp_list.append(tmp_dict)
                n += 1
            except Exception:
                logging.error(f"Line {i+1}: {split_line}")
                logging.error(f"{red}your log may be corrupted{normal}")
                sys.exit(1)
        else:
            logging.error(f"{red}Unparsed line{normal} {i} `{line}'")

    if s:
        logging.debug(f'{s} skipped test set(s)')

    return temp_list


# Parse Seq file, used to tell which tests should run.
def seq_parser(file: IO[str]) -> list[dict[str, str]]:
    temp = []
    lines = file.readlines()
    magic = 7
    # a test in a seq file is 7 lines, if not mod7, something wrong..
    if len(lines) % magic != 0:
        logging.error(f"{red}seqfile cut short{normal}, should be mod7")
        sys.exit(1)
    # the utf-16 char makes this looping a bit harder, so we use x+(i) where i
    # is next 0-6th
    # loop ever "7 lines"
    for x in range(0, len(lines), magic):
        # (x+0)[Test Case]
        # (x+1)Revision=0x10000
        # (x+2)Guid=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
        # (x+3)Name=InstallAcpiTableFunction
        # (x+4)Order=0xFFFFFFFF
        # (x+5)Iterations=0xFFFFFFFF
        # (x+6)(utf-16 char)
        # currently only add tests that are supposed to run, should add all?
        # 0xFFFFFFFF in "Iterations" means the test is NOT supposed to run
        if "0xFFFFFFFF" not in lines[x + 5]:
            seq_dict = {
                # from after "Name=" to end (5char long)
                "name": lines[x + 3][5:-1],
                # from after"Guid=" to the end, (5char long)
                "guid": lines[x + 2][5:-1],
                # from after "Iterations=" (11char long)
                "Iteration": lines[x + 5][11:-1],
                # from after "Revision=" (9char long)
                "rev": lines[x + 1][9:-1],
                # from after "Order=" (6char long)
                "Order": lines[x + 4][6:-1]
            }
            temp.append(seq_dict)

    return temp


# Print items by "group"
def key_tree_2_md(input_list: list[dict[str, str]], file: IO[str]) -> None:
    h: dict[str, list[dict[str, str]]] = {}

    # Bin by group
    for t in input_list:
        g = t['group']

        if g not in h:
            h[g] = []

        h[g].append(t)

    # Print each group
    for g in sorted(h.keys()):
        file.write("### " + g)
        dict_2_md(h[g], file)


# generic writer, takes a list of dicts and turns the dicts into an MD table.
def dict_2_md(input_list: list[dict[str, str]], file: IO[str]) -> None:
    if len(input_list) > 0:
        file.write("\n\n")
        k = input_list[0].keys()
        # create header for MD table using dict keys
        temp_string1, temp_string2 = "|", "|"
        for x in k:
            temp_string1 += (x + "|")
            temp_string2 += ("---|")
        file.write(temp_string1 + "\n" + temp_string2 + "\n")
        # print each item from the dict into the table
        for w in input_list:
            test_string = "|"
            for y in k:
                v = w[y] if y in w else ''
                test_string += v + "|"
            file.write(test_string + '\n')
    # seprate table from other items in MD
    file.write("\n\n")


# Sanitize our YAML configuration
# We modify conf in-place
def sanitize_yaml(conf: ConfigType) -> None:
    rules = set()

    for i, r in enumerate(conf):
        # Generate a rule name if needed
        if 'rule' not in r:
            r['rule'] = f'r{i}'
            logging.debug(f"Auto-naming rule {i} `{r['rule']}'")
            conf[i] = r

        if r['rule'] in rules:
            logging.warning(
                f"{yellow}Duplicate rule{normal} {i} `{r['rule']}'")

        rules.add(r['rule'])

        if 'criteria' not in r or not isinstance(r['criteria'], dict) or \
           'update' not in r or not isinstance(r['update'], dict):
            logging.error(f"{red}Bad rule{normal} {i} `{r}'")
            raise Exception()


# Evaluate if a test dict matches a criteria
# The criteria is a dict of Key-value pairs.
# I.E. crit = {"result": "FAILURE", "xxx": "yyy", ...}
# All key-value pairs must be present and match for a test dict to match.
# A test value and a criteria value match if the criteria value string is
# present anywhere in the test value string.
# For example, the test value "abcde" matches the criteria value "cd".
# This allows for more "relaxed" criteria than strict comparison.
def matches_crit(test: DbEntry, crit: DbEntry) -> bool:
    for key, value in crit.items():
        if key not in test or test[key].find(value) < 0:
            return False

    return True


# Apply all configuration rules to the tests
# We modify cross_check in-place
def apply_rules(cross_check: DbType, conf: ConfigType) -> None:
    # Prepare statistics counters
    stats = {}

    for r in conf:
        stats[r['rule']] = 0

    # Apply rules on each test data
    s = len(cross_check)

    for i in range(s):
        test = cross_check[i]

        for r in conf:
            if not matches_crit(test, r['criteria']):
                continue

            rule = r['rule']

            logging.debug(
                f"Applying rule `{rule}'"
                f" to test {i} `{test['name']}'")

            test.update({
                **r['update'],
                'Updated by': rule,
            })

            stats[rule] += 1
            break

    # Statistics
    n = 0

    for rule, cnt in stats.items():
        logging.debug(f"{cnt} matche(s) for rule `{rule}'")
        n += cnt

    if n:
        x = len(conf)
        logging.info(
            f"Updated {n} {maybe_plural(n, 'test')} out of {s}"
            f" after applying {x} {maybe_plural(x, 'rule')}")


# Load YAML configuration file
# See the README.md for details on the configuration file format.
def load_config(filename: str) -> ConfigType:
    # Load configuration file
    logging.debug(f'Read {filename}')

    with open(filename, 'r') as yamlfile:
        y = yaml.load(yamlfile, **yaml_load_args)
        conf = cast(Optional[ConfigType], y)

    if conf is None:
        conf = []

    logging.debug(f"{len(conf)} rule(s)")
    sanitize_yaml(conf)
    return conf


# Filter tests data
# Filter is a python expression, which is evaluated for each test
# When the expression evaluates to True, the test is kept
# Otherwise it is dropped
def filter_data(cross_check: DbType, Filter: str) -> DbType:
    logging.debug(f"Filtering with `{Filter}'")
    before = len(cross_check)

    # This function "wraps" the filter and is called for each test
    # `x' is referred to from the filter expression.
    def function(x: DbEntry) -> bool:
        # pylint: disable=unused-argument eval-used
        return bool(eval(Filter))

    r = list(filter(function, cross_check))
    after = len(r)
    n = before - after
    logging.info(f"Filtered out {n} {maybe_plural(n, 'test')}, kept {after}")
    return r


# Sort tests data in-place
# sort_keys is a comma-separated list
# The first key has precedence, then the second, etc.
# To use python list in-place sorting, we use the keys in reverse order.
def sort_data(cross_check: DbType, sort_keys: str) -> None:
    logging.debug(f"Sorting on `{sort_keys}'")

    def key_func(k: str) -> Callable[[dict[str, str]], str]:
        def func(x: dict[str, str]) -> str:
            return x[k]

        return func

    for k in reversed(sort_keys.split(',')):
        cross_check.sort(key=key_func(k))


# Keep only certain fields in data, in-place
# The fields to write are supplied as a comma-separated list
def keep_fields(cross_check: DbType, fields: str) -> None:
    logging.debug(f"Keeping fields: `{fields}'")
    s = set(fields.split(','))

    for x in cross_check:
        for k in list(x.keys()):
            if k not in s:
                del x[k]


# Do a "uniq" pass on the data
# All duplicate entries are collapsed into a single one
# We add a "count" field
def uniq(cross_check: DbType) -> DbType:
    logging.debug("Collapsing duplicates")

    # First pass to count all occurences
    h: dict[str, DbEntry] = {}

    for x in cross_check:
        i = ''

        for k in sorted(x.keys()):
            i += f"{k}:{x[k]} "

        if i not in h:
            h[i] = {
                'count': '0',
                **x,
            }

        # Increment count but keep it as a string.
        h[i]['count'] = str(int(h[i]['count']) + 1)

    # Transform back to list
    r = list(h.values())
    logging.info(f"{len(r)} unique entries")
    return r


# Discover fields
# The fields can be supplied as a comma-separated list
# Order is preserved
# Additional fields are auto-discovered and added to the list, sorted
def discover_fields(
        cross_check: DbType, fields: Optional[str] = None) -> list[str]:

    if fields is not None:
        keys = fields.split(',')
    else:
        keys = []

    # Find keys, not already listed
    s: set[str] = set()

    for x in cross_check:
        s = s.union(x.keys())

    s = s.difference(keys)
    keys += sorted(s)

    logging.debug(f'Fields: {keys}')
    return keys


# Generate csv
# The fields to write are supplied as a list
def gen_csv(cross_check: DbType, filename: str, fields: list[str]) -> None:
    logging.debug(f'Generate {filename} (fields: {fields})')

    with open(filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(
            csvfile, fieldnames=fields, delimiter=';')
        writer.writeheader()
        writer.writerows(cross_check)


# Generate json
def gen_json(cross_check: DbType, filename: str) -> None:
    logging.debug(f'Generate {filename}')

    with open(filename, 'w') as jsonfile:
        json.dump(cross_check, jsonfile, sort_keys=True, indent=2)


# Generate junit
def gen_junit(cross_check: DbType, filename: str) -> None:
    assert 'junit_xml' in sys.modules
    logging.debug(f'Generate {filename}')

    testsuites = {}

    for result in cross_check:
        testcase = TestCase(
            result['name'] if result['name'] else result['sub set'],
            (result['test set'] if result['test set'] else
                result['set guid']) + "." + result['sub set'],
            0,
            "Description: " + result['descr'] +
            "\nSet GUID: " + result['set guid'] +
            "\nGUID: " + result['guid'] +
            "\nDevice Path: " + result['device path'] +
            "\nStart Date: " + result['start date'] +
            "\nStart Time: " + result['start time'] +
            "\nRevision: " + result['revision'] +
            "\nIteration: " + result['iteration'] +
            "\nLog: " + result['log'],
            "")
        if result['result'] == 'FAILURE':
            testcase.add_failure_info(result['result'])
        elif result['result'] == 'SKIPPED':
            testcase.add_skipped_info(result['result'])
        elif result['result'] == 'DROPPED':
            testcase.add_skipped_info(result['result'])

        group = result['group'] if result['group'] else result['test set']
        if group not in testsuites:
            testsuites[group] = TestSuite(group)

        testsuites[group].test_cases.append(testcase)

    with open(filename, 'w') as file:
        TestSuite.to_file(file, testsuites.values())


# Write meta-data to YAML file as comments.
def yaml_meta(f: IO[str], meta: MetaData) -> None:
    print('# Meta-data:', file=f)

    for k in sorted(meta.keys()):
        print(f"# {k}: {meta[k]}", file=f)

    print('', file=f)


# Generate yaml
# We output meta-data as comments.
def gen_yaml(cross_check: DbType, filename: str, meta: MetaData) -> None:
    logging.debug(f'Generate {filename}')

    with open(filename, 'w') as yamlfile:
        yaml_meta(yamlfile, meta)
        yaml.dump(cross_check, yamlfile, Dumper=Dumper)


# Generate yaml config template
# This is to help writing yaml config.
# We omit tests with result PASS.
# We omit some tests keys: iteration and dates.
# We remove the leading directory from C filename in log.
# We output meta-data as comments.
def gen_template(cross_check: DbType, filename: str, meta: MetaData) -> None:
    logging.debug(f'Generate {filename}')
    omitted_keys = set(['iteration', 'start date', 'start time'])
    t = []
    i = 1

    for x in cross_check:
        if x['result'] == 'PASS':
            continue

        r: ConfigEntry = {
            'rule': f'Generated rule ({i})',
            'criteria': {},
            'update': {'result': 'TEMPLATE'},
        }

        for key, value in x.items():
            if key in omitted_keys:
                continue

            if key == 'log':
                value = re.sub(r'^/.*/', '', str(value))

            r['criteria'][key] = value

        t.append(r)
        i += 1

    with open(filename, 'w') as yamlfile:
        yaml_meta(yamlfile, meta)
        yaml.dump(t, yamlfile, Dumper=Dumper)


# Print to stdout
# The fields to write are supplied as a list
# We handle the case where not all fields are present for all records
def do_print(cross_check: DbType, fields: list[str]) -> None:
    logging.debug(f'Print (fields: {fields})')

    # First pass to find the width for each field
    w = {}

    for f in fields:
        w[f] = len(f)

    for x in cross_check:
        for f in fields:
            w[f] = max(w[f], len(str(x[f]) if f in x else ''))

    # Second pass where we print
    fm1 = fields[:len(fields) - 1]
    lf = fields[len(fields) - 1]
    sep = '  '

    print(sep.join([
        *map(lambda f: f"{f.capitalize():{w[f]}}", fm1),
        lf.capitalize()]))

    print(sep.join([*map(lambda f: '-' * w[f], fields)]))

    def map_func(x: dict[str, str]) -> Callable[[str], str]:
        def func(f: str) -> str:
            return f"{x[f] if f in x else '':{w[f]}}"

        return func

    for x in cross_check:
        print(sep.join([*map(map_func(x), fm1), x[lf] if lf in x else '']))


# Combine or two databases db1 and db2 coming from ekl and seq files
# respectively into a single cross_check database
# Tests in db1, which were not meant to be run according to db2 have their
# results forced to SPURIOUS.
# Tests sets in db2, which were not run according to db1 have an artificial
# test entry created with result DROPPED.
def combine_dbs(db1: DbType, db2: DbType) -> DbType:
    cross_check = db1

    # Do a pass to verify that all tests in db1 were meant to be run.
    # Otherwise, force the result to SPURIOUS.
    s = set()

    for x in db2:
        s.add(x['guid'])

    n = 0

    for i, x in enumerate(cross_check):
        if x['set guid'] not in s:
            logging.debug(f"Spurious test {i} `{cross_check[i]['name']}'")
            x['result'] = 'SPURIOUS'
            n += 1

    if n:
        logging.debug(f'{n} spurious test(s)')

    # Do a pass to find the test sets that did not run for whatever reason.
    s = set()

    for x in cross_check:
        s.add(x['set guid'])

    n = 0

    for i, x in enumerate(db2):
        if not x['guid'] in s:
            logging.debug(f"Dropped test set {i} `{x['name']}'")

            # Create an artificial test entry to reflect the dropped test set
            cross_check.append({
                'descr': '',
                'device path': '',
                'guid': '',
                'iteration': '',
                'log': '',
                'name': '',
                'start date': '',
                'start time': '',
                'test set': '',
                'sub set': x['name'],
                'set guid': x['guid'],
                'revision': x['rev'],
                'group': 'Unknown',
                'result': 'DROPPED',
            })

            n += 1

    if n:
        logging.debug(f'{n} dropped test set(s)')

    return cross_check


# Verify Sanity of our YAML seq db
def sanity_check_seq_db(seq_db: SeqDb) -> None:
    assert 'seq_db' in seq_db
    s = set()

    for x in seq_db['seq_files']:
        sha = x['sha256']
        assert sha not in s
        s.add(sha)


# Load the database of known sequence files.
def load_seq_db(filename: str) -> SeqDb:
    logging.debug(f'Read {filename}')

    with open(filename, 'r') as yamlfile:
        y = yaml.load(yamlfile, **yaml_load_args)
        seq_db = cast(Optional[SeqDb], y)

    if seq_db is None:
        seq_db = {'seq_db': None, 'seq_files': []}

    sanity_check_seq_db(seq_db)
    logging.debug(f"{len(seq_db['seq_files'])} known seq file(s)")
    return seq_db


# Try to identify the .seq file in a list of known versions using its sha256.
# We return the identified seq_db entry or None.
def ident_seq(seq_file: str, seq_db_name: str) -> Optional[SeqFile]:
    seq_db = load_seq_db(seq_db_name)

    # Hash seq file
    hm = 'sha256'
    hl = hashlib.new(hm)

    with open(seq_file, 'rb') as f:
        hl.update(f.read())

    h = hl.hexdigest()
    logging.debug(f'{hm} {h} {seq_file}')

    # Try to identify the seq file
    for x in seq_db['seq_files']:
        if x['sha256'] == h:
            logging.info(
                f"""{green}Identified{normal} `{seq_file}'"""
                f""" as "{x['name']}".""")

            if 'deprecated' in x:
                logging.warning(
                    f"{yellow}This sequence file is deprecated!{normal}")

            return x

    logging.warning(f"{yellow}Could not identify{normal} `{seq_file}'...")
    return None


# Read the .ekl log file and the .seq file and combine them into a single
# database, which we return.
def read_log_and_seq(log_file: str, seq_file: str) -> DbType:
    # ekl file to open
    # "database 1" all tests.
    logging.debug(f'Read {log_file}')

    # files are encoded in utf-16
    with open(log_file, "r", encoding="utf-16") as f:
        db1 = ekl_parser(f.readlines())

    logging.debug(f"{len(db1)} test(s)")

    # seq file to open
    # "database 2" all test sets that should run
    logging.debug(f'Read {seq_file}')

    # files are encoded in utf-16
    with open(seq_file, "r", encoding="utf-16") as f:
        db2 = seq_parser(f)

    logging.debug(f"{len(db2)} test set(s)")

    # Produce a single cross_check database from our two db1 and db2 databases.
    return combine_dbs(db1, db2)


# generate MD summary
# We output meta-data
def gen_md(
        md: str, res_keys: set[str], bins: BinsType, meta: MetaData) -> None:

    logging.debug(f'Generate {md}')

    with open(md, 'w') as resultfile:
        resultfile.write("# SCT Summary\n\n")
        resultfile.write("|Result|Test(s)|\n")
        resultfile.write("|--|--|\n")

        # Loop on all the result values we found for the summary
        for k in sorted(res_keys):
            resultfile.write(f"|{k.title()}:|{len(bins[k])}|\n")

        resultfile.write("\n\n")

        # Loop on all the result values we found (except PASS) for the sections
        # listing the tests by group
        n = 1
        res_keys_np = set(res_keys)
        res_keys_np.remove('PASS')

        for k in sorted(res_keys_np):
            resultfile.write(f"## {n}. {k.title()} by group\n\n")
            key_tree_2_md(bins[k], resultfile)
            n += 1

        # Meta-data
        resultfile.write('## Meta-data\n\n')
        resultfile.write("|  |  |\n")
        resultfile.write("|--|--|\n")

        for k in sorted(meta.keys()):
            resultfile.write(f"|{k}:|{meta[k]}|\n")


# Read back results from a previously generated summary markdown file.
# From this, we re-create a database the best we can and we return it.
def read_md(input_md: str) -> DbType:
    logging.debug(f'Read {input_md}')
    tables = []

    with open(input_md, 'r') as f:
        t: Optional[list[list[str]]] = None

        for i, line in enumerate(f):
            line = line.rstrip()

            if re.match(r'^\|', line):
                # Split the line. We need to take care of preserving special
                # cases such as "Pci(0|0)" for example
                line = re.sub(r'\((\w+)\|(\w+)\)', r'(\1%\2)', line)
                x = line.split('|')
                x = x[1:len(x) - 1]
                x = [re.sub(r'%', '|', e) for e in x]

                if t is None:
                    t = []
                    logging.debug(f'Table line {i + 1}, keys: {x}')

                t.append(x)

            elif t is not None:
                tables.append(t)
                t = None

        if t is not None:
            tables.append(t)

    # Remove all small tables, such as the summary and meta-data tables
    tables2 = filter(lambda x: len(x[0]) > 2, tables)

    # Transform tables lines to dicts and merge everything
    cross_check = []

    for t in tables2:
        # Save keys
        keys = t.pop(0)
        n = len(keys)
        # Drop underlines
        t.pop(0)

        # Convert lines
        for i, x in enumerate(t):
            assert len(x) == n
            y = {}

            for j, k in enumerate(keys):
                y[k] = x[j]

            cross_check.append(y)

    return cross_check


# Print a one-line summary
# We know how to colorize some categories when they are non-zero.
def print_summary(bins: BinsType, res_keys: set[str]) -> None:
    colors = {
        'DROPPED': red,
        'FAILURE': red,
        'PASS': green,
        'SKIPPED': yellow,
        'WARNING': yellow,
    }

    d = {}

    for k in res_keys:
        n = len(bins[k])
        d[k] = f'{n} {maybe_plural(n, k.lower())}'

        if n > 0 and k in colors:
            d[k] = f'{colors[k]}{d[k]}{normal}'

    logging.info(', '.join(map(lambda k: d[k], sorted(res_keys))))


# Return a dict with the initial meta-data.
def meta_data(argv: list[str], here: str) -> MetaData:
    r: MetaData = {
        'command-line': ' '.join(argv),
        'date': f"{time.asctime(time.gmtime())} UTC",
    }

    cp = subprocess.run(
        f"git -C '{here}' describe --always --abbrev=12 --dirty", shell=True,
        capture_output=True, check=False)
    logging.debug(cp)

    if cp.returncode:
        logging.debug('No git')
    else:
        r['git-commit'] = cp.stdout.decode().rstrip()

    logging.debug(f"meta-data: {r}")
    return r


# Perform some sanity checks on the tests:
# - We verify that the tests have all the fields we need.
def sanity_check(cross_check: DbType) -> None:
    fields = [
        'descr',
        'device path',
        'guid',
        'iteration',
        'log',
        'name',
        'start date',
        'start time',
        'test set',
        'sub set',
        'set guid',
        'revision',
        'group',
        'result',
    ]

    for x in cross_check:
        for f in fields:
            assert f in x


if __name__ == '__main__':
    me = os.path.realpath(__file__)
    here = os.path.dirname(me)
    parser = argparse.ArgumentParser(
        description='Process SCT results.'
                    ' This program takes the SCT summary and sequence files,'
                    ' and generates a nice report in mardown format.',
        epilog='When sorting is requested, tests data are sorted'
               ' according to the first sort key, then the second, etc.'
               ' Sorting happens after update by the configuration rules.'
               ' Useful example: --sort'
               ' "group,descr,set guid,test set,sub set,guid,name,log"'
               ' When not validating a configuration file, an input .ekl and'
               ' an input .seq files are required.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--csv', help='Output .csv filename')
    parser.add_argument('--json', help='Output .json filename')

    # junit-xml modules must of been loaded to enable the --junit option
    if 'junit_xml' in sys.modules:
        parser.add_argument('--junit', help='Output .junit filename')

    parser.add_argument(
        '--md', help='Output .md filename', default='result.md')
    parser.add_argument(
        '--debug', action='store_true', help='Turn on debug messages')
    parser.add_argument(
        '--sort', help='Comma-separated list of keys to sort output on')
    parser.add_argument('--filter', help='Python expression to filter results')
    parser.add_argument(
        '--fields', help='Comma-separated list of fields to write')
    parser.add_argument(
        '--uniq', action='store_true', help='Collapse duplicates')
    parser.add_argument(
        '--print', action='store_true', help='Print results to stdout')
    parser.add_argument(
        '--print-meta', action='store_true', help='Print meta-data to stdout')
    parser.add_argument('--input-md', help='Input .md filename')
    parser.add_argument(
        '--seq-db', help='Known sequence files database filename',
        default=f'{here}/seq_db.yaml')
    parser.add_argument('log_file', nargs='?', help='Input .ekl filename')
    parser.add_argument('seq_file', nargs='?', help='Input .seq filename')
    parser.add_argument('find_key', nargs='?', help='Search key')
    parser.add_argument('find_value', nargs='?', help='Search value')
    parser.add_argument('--config', help='Input .yaml configuration filename')
    parser.add_argument('--yaml', help='Output .yaml filename')
    parser.add_argument(
        '--template', help='Output .yaml config template filename')
    args = parser.parse_args()

    logging.basicConfig(
        format='%(levelname)s %(funcName)s: %(message)s',
        level=logging.DEBUG if args.debug else logging.INFO)

    ln = logging.getLevelName(logging.WARNING)
    logging.addLevelName(logging.WARNING, f"{yellow}{ln}{normal}")
    ln = logging.getLevelName(logging.ERROR)
    logging.addLevelName(logging.ERROR, f"{red}{ln}{normal}")

    # We must have a log file and a seq file.
    if args.log_file is None:
        logging.error("No input .ekl!")
        sys.exit(1)
    if args.seq_file is None:
        logging.error("No input .seq!")
        sys.exit(1)

    # First part of configuration selection: command line, or default.
    # We need to do this early for the case of config validation.
    if args.config is not None:
        config = args.config
    else:
        config = f'{here}/EBBR.yaml'

    # Prepare initial meta-data.
    meta = meta_data(sys.argv, here)

    if args.input_md is not None:
        cross_check = read_md(args.input_md)
        ident = None
    else:
        # Command line argument 1 is the ekl file to open.
        # Command line argument 2 is the seq file to open.

        # Try to identify the sequence file
        ident = ident_seq(args.seq_file, args.seq_db)

        if ident is not None:
            meta['seq-file-ident'] = ident['name']

        # Read both and combine them into a single cross_check database.
        cross_check = read_log_and_seq(args.log_file, args.seq_file)

    logging.debug(f"{len(cross_check)} combined test(s)")

    # Perform some sanity checks on the tests.
    sanity_check(cross_check)

    # Second part of configuration file selection: take autodetect into account
    # but with less priority than command line.
    if args.config is None and ident is not None:
        config = f"{here}/{ident['config']}"

    # Take configuration file into account. This can perform transformations on
    # the tests results.
    logging.debug(f"Read config `{config}'")
    conf = load_config(config)
    apply_rules(cross_check, conf)

    # Filter tests data, if requested
    if args.filter is not None:
        cross_check = filter_data(cross_check, args.filter)

    # Sort tests data in-place, if requested
    if args.sort is not None:
        sort_data(cross_check, args.sort)

    # search for failures, warnings, passes & others
    # We detect all present keys in additions to the expected ones. This is
    # handy with config rules overriding the result field
    # with arbitrary values.
    res_keys = set(['DROPPED', 'FAILURE', 'WARNING', 'PASS'])

    for x in cross_check:
        res_keys.add(x['result'])

    # Now we fill some bins with tests according to their result
    bins = {}

    for k in res_keys:
        bins[k] = key_value_find(cross_check, "result", k)

    # Print a one-line summary
    print_summary(bins, res_keys)

    # Print meta-data
    if args.print_meta:
        print()
        print('meta-data')
        print('---------')
        for k in sorted(meta.keys()):
            print(f"{k}: {meta[k]}")

    # generate MD summary
    # As a special case, we skip generation when we are reading from a markdown
    # summary, which has the same name as the output.
    if args.input_md is None or args.input_md != args.md:
        gen_md(args.md, res_keys, bins, meta)

    # Generate yaml config template if requested
    if args.template is not None:
        gen_template(cross_check, args.template, meta)

    # Filter fields before writing any other type of output
    # Do not rely on specific fields being present after this step
    if args.fields is not None:
        keep_fields(cross_check, args.fields)

    # Do a `uniq` pass if requested
    if args.uniq:
        cross_check = uniq(cross_check)

    # Auto-discover the fields and take the option into account
    fields = discover_fields(cross_check, args.fields)

    # Generate csv if requested
    if args.csv is not None:
        gen_csv(cross_check, args.csv, fields)

    # Generate json if requested
    if args.json is not None:
        gen_json(cross_check, args.json)

    # Generate junit if requested
    if 'junit' in args and args.junit is not None:
        gen_junit(cross_check, args.junit)

    # Generate yaml if requested
    if args.yaml is not None:
        gen_yaml(cross_check, args.yaml, meta)

    # Print if requested
    if args.print:
        do_print(cross_check, fields)

    # command line argument 3&4, key are to support a key & value search.
    # these will be displayed in CLI
    if args.find_key is not None and args.find_value is not None:
        found = key_value_find(cross_check, args.find_key, args.find_value)
        # print the dict
        print("found:", len(found), "items with search constraints")
        for x in found:
            print(
                x["guid"], ":", x["name"], "with", args.find_key, ":",
                x[args.find_key])
