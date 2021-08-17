#!/usr/bin/env python3
# SCT log parser


import sys
import argparse
import csv
import logging
import json
import re

try:
    from packaging import version
except ImportError:
    print('No packaging...')

try:
    import yaml
except ImportError:
    print('No yaml...')

if 'yaml' in sys.modules:
    try:
        from yaml import CDumper as Dumper
    except ImportError:
        from yaml import Dumper

# Not all yaml versions have a Loader argument.
if 'packaging.version' in sys.modules and \
   version.parse(yaml.__version__) >= version.parse('5.1'):
    yaml_load_args = {'Loader': yaml.FullLoader}
else:
    yaml_load_args = {}


# based loosley on https://stackoverflow.com/a/4391978
# returns a filtered dict of dicts that meet some Key-value pair.
# I.E. key="result" value="FAILURE"
def key_value_find(list_1, key, value):
    found = list()
    for test in list_1:
        if test[key] == value:
            found.append(test)
    return found


# Were we intrept test logs into test dicts
def test_parser(string, current):
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
def ekl_parser(file):
    # create our "database" dict
    temp_list = list()
    # All tests are grouped by the "HEAD" line, which precedes them.
    current = {}

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
                print(f"Line {i+1}:", split_line)
                sys.exit("your log may be corrupted")
        else:
            logging.error(f"Unparsed line {i} `{line}'")

    if s:
        logging.debug(f'{s} skipped test set(s)')

    return temp_list


# Parse Seq file, used to tell which tests should run.
def seq_parser(file):
    temp_dict = list()
    lines = file.readlines()
    magic = 7
    # a test in a seq file is 7 lines, if not mod7, something wrong..
    if len(lines) % magic != 0:
        sys.exit("seqfile cut short, should be mod7")
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
            # put in a dict based on guid
            temp_dict.append(seq_dict)

    return temp_dict


# Print items by "group"
def key_tree_2_md(input_list, file):
    h = {}

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
def dict_2_md(input_list, file):
    if len(input_list) > 0:
        file.write("\n\n")
        # create header for MD table using dict keys
        temp_string1, temp_string2 = "|", "|"
        for x in (input_list[0].keys()):
            temp_string1 += (x + "|")
            temp_string2 += ("---|")
        file.write(temp_string1 + "\n" + temp_string2 + "\n")
        # print each item from the dict into the table
        for x in input_list:
            test_string = "|"
            for y in x.keys():
                test_string += (x[y] + "|")
            file.write(test_string + '\n')
    # seprate table from other items in MD
    file.write("\n\n")


# Sanitize our YAML configuration
# We modify conf in-place
# TODO: use a proper validator instead
def sanitize_yaml(conf):
    rules = set()

    for i in range(len(conf)):
        r = conf[i]

        # Generate a rule name if needed
        if 'rule' not in r:
            r['rule'] = f'r{i}'
            logging.debug(f"Auto-naming rule {i} `{r['rule']}'")
            conf[i] = r

        if r['rule'] in rules:
            logging.warning(f"Duplicate rule {i} `{r['rule']}'")

        rules.add(r['rule'])

        if 'criteria' not in r or not type(r['criteria']) is dict or \
           'update' not in r or not type(r['update']) is dict:
            logging.error(f"Bad rule {i} `{r}'")
            raise Exception()


# Evaluate if a test dict matches a criteria
# The criteria is a dict of Key-value pairs.
# I.E. crit = {"result": "FAILURE", "xxx": "yyy", ...}
# All key-value pairs must be present and match for a test dict to match.
# A test value and a criteria value match if the criteria value string is
# present anywhere in the test value string.
# For example, the test value "abcde" matches the criteria value "cd".
# This allows for more "relaxed" criteria than strict comparison.
def matches_crit(test, crit):
    for key, value in crit.items():
        if key not in test or test[key].find(value) < 0:
            return False

    return True


# Apply all configuration rules to the tests
# We modify cross_check in-place
def apply_rules(cross_check, conf):
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
        r = len(conf)
        logging.info(
            f'Updated {n} test(s) out of {s} after applying {r} rule(s)')


# Use YAML configuration file and perform all the transformations described in
# there.
# See the README.md for details on the file format.
# We modify cross_check in-place
def use_config(cross_check, filename):
    assert('yaml' in sys.modules)

    # Load configuration file
    logging.debug(f'Read {filename}')

    with open(filename, 'r') as yamlfile:
        conf = yaml.load(yamlfile, **yaml_load_args)

    logging.debug('{} rule(s)'.format(len(conf)))
    sanitize_yaml(conf)
    apply_rules(cross_check, conf)


# Filter tests data
# Filter is a python expression, which is evaluated for each test
# When the expression evaluates to True, the test is kept
# Otherwise it is dropped
def filter_data(cross_check, Filter):
    logging.debug(f"Filtering with `{Filter}'")
    before = len(cross_check)

    # This function "wraps" the filter and is called for each test
    def function(x):
        return eval(Filter)

    r = list(filter(function, cross_check))
    after = len(r)
    logging.info(f"Filtered out {before - after} test(s), kept {after}")
    return r


# Sort tests data in-place
# sort_keys is a comma-separated list
# The first key has precedence, then the second, etc.
# To use python list in-place sorting, we use the keys in reverse order.
def sort_data(cross_check, sort_keys):
    logging.debug(f"Sorting on `{sort_keys}'")
    for k in reversed(sort_keys.split(',')):
        cross_check.sort(key=lambda x: x[k])


# Keep only certain fields in data, in-place
# The fields to write are supplied as a comma-separated list
def keep_fields(cross_check, fields):
    logging.debug(f"Keeping fields: `{fields}'")
    s = set(fields.split(','))

    for x in cross_check:
        for k in list(x.keys()):
            if k not in s:
                del x[k]


# Do a "uniq" pass on the data
# All duplicate entries are collapsed into a single one
# We add a "count" field
def uniq(cross_check):
    logging.debug("Collapsing duplicates")

    # First pass to count all occurences
    h = {}

    for x in cross_check:
        i = ''

        for k in sorted(x.keys()):
            i += f"{k}:{x[k]} "

        if i not in h:
            h[i] = {
                'count': 0,
                **x,
            }

        h[i]['count'] += 1

    # Transform back to list
    r = list(h.values())
    logging.info(f"{len(r)} unique entries")
    return r


# Discover fields
# The fields can be supplied as a comma-separated list
# Order is preserved
# Additional fields are auto-discovered and added to the list, sorted
def discover_fields(cross_check, fields=None):
    if fields is not None:
        keys = fields.split(',')
    else:
        keys = []

    # Find keys, not already listed
    s = set()

    for x in cross_check:
        s = s.union(x.keys())

    s = s.difference(keys)
    keys += sorted(s)

    logging.debug(f'Fields: {keys}')
    return keys


# Generate csv
# The fields to write are supplied as a list
def gen_csv(cross_check, filename, fields):
    logging.debug(f'Generate {filename} (fields: {fields})')

    with open(filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(
            csvfile, fieldnames=fields, delimiter=';')
        writer.writeheader()
        writer.writerows(cross_check)


# Generate json
def gen_json(cross_check, filename):
    logging.debug(f'Generate {filename}')

    with open(filename, 'w') as jsonfile:
        json.dump(cross_check, jsonfile, sort_keys=True, indent=2)


# Generate yaml
def gen_yaml(cross_check, filename):
    assert('yaml' in sys.modules)
    logging.debug(f'Generate {filename}')

    with open(filename, 'w') as yamlfile:
        yaml.dump(cross_check, yamlfile, Dumper=Dumper)


# Generate yaml config template
# This is to help writing yaml config.
# We omit tests with result PASS.
# We omit some tests keys: iteration and dates.
# We remove the leading directory from C filename in log.
def gen_template(cross_check, filename):
    assert('yaml' in sys.modules)
    logging.debug(f'Generate {filename}')
    omitted_keys = set(['iteration', 'start date', 'start time'])
    t = []
    i = 1

    for x in cross_check:
        if x['result'] == 'PASS':
            continue

        r = {
            'rule': f'Generated rule ({i})',
            'criteria': {},
            'update': {'result': 'TEMPLATE'},
        }

        for key, value in x.items():
            if key in omitted_keys:
                continue

            if key == 'log':
                value = re.sub(r'^/.*/', '', value)

            r['criteria'][key] = value

        t.append(r)
        i += 1

    with open(filename, 'w') as yamlfile:
        yaml.dump(t, yamlfile, Dumper=Dumper)


# Print to stdout
# The fields to write are supplied as a list
def do_print(cross_check, fields):
    logging.debug(f'Print (fields: {fields})')

    # First pass to find the width for each field except the last one
    fm1 = fields[:len(fields) - 1]
    w = {}

    for f in fm1:
        w[f] = len(f)

    for x in cross_check:
        for f in fm1:
            w[f] = max(w[f], len(str(x[f])))

    # Second pass where we print
    lf = fields[len(fields) - 1]

    print(' '.join([
        *map(lambda f: f"{f:{w[f]}}", fm1),
        lf]))

    for x in cross_check:
        print(' '.join([
            *map(lambda f: f"{x[f]:{w[f] if f in x else ''}}", fm1),
            x[lf] if lf in x else '']))


# Combine or two databases db1 and db2 coming from ekl and seq files
# respectively into a single cross_check database
# Tests in db1, which were not meant to be run according to db2 have their
# results forced to SPURIOUS.
# Tests sets in db2, which were not run according to db1 have an artificial
# test entry created with result DROPPED.
def combine_dbs(db1, db2):
    cross_check = db1

    # Do a pass to verify that all tests in db1 were meant to be run.
    # Otherwise, force the result to SPURIOUS.
    s = set()

    for x in db2:
        s.add(x['guid'])

    n = 0

    for i in range(len(cross_check)):
        if cross_check[i]['set guid'] not in s:
            logging.debug(f"Spurious test {i} `{cross_check[i]['name']}'")
            cross_check[i]['result'] = 'SPURIOUS'
            n += 1

    if n:
        logging.debug(f'{n} spurious test(s)')

    # Do a pass to autodetect all tests fields in case we need to merge dropped
    # tests sets entries
    f = {}

    for x in cross_check:
        for k in x.keys():
            f[k] = ''

    logging.debug(f'Test fields: {f.keys()}')

    # Do a pass to find the test sets that did not run for whatever reason.
    s = set()

    for x in cross_check:
        s.add(x['set guid'])

    n = 0

    for i in range(len(db2)):
        x = db2[i]

        if not x['guid'] in s:
            logging.debug(f"Dropped test set {i} `{x['name']}'")

            # Create an artificial test entry to reflect the dropped test set
            cross_check.append({
                **f,
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


# Read the .ekl log file and the .seq file and combine them into a single
# database, which we return.
def read_log_and_seq(log_file, seq_file):
    # ekl file to open
    # "database 1" all tests.
    db1 = list()
    logging.debug(f'Read {log_file}')

    # files are encoded in utf-16
    with open(log_file, "r", encoding="utf-16") as f:
        db1 = ekl_parser(f.readlines())

    logging.debug('{} test(s)'.format(len(db1)))

    # seq file to open
    # "database 2" all test sets that should run
    db2 = dict()
    logging.debug(f'Read {seq_file}')

    # files are encoded in utf-16
    with open(seq_file, "r", encoding="utf-16") as f:
        db2 = seq_parser(f)

    logging.debug('{} test set(s)'.format(len(db2)))

    # Produce a single cross_check database from our two db1 and db2 databases.
    return combine_dbs(db1, db2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Process SCT results.'
                    ' This program takes the SCT summary and sequence files,'
                    ' and generates a nice report in mardown format.',
        epilog='When sorting is requested, tests data are sorted'
               ' according to the first sort key, then the second, etc.'
               ' Sorting happens after update by the configuration rules.'
               ' Useful example: --sort'
               ' "group,descr,set guid,test set,sub set,guid,name,log"',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--csv', help='Output .csv filename')
    parser.add_argument('--json', help='Output .json filename')
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
    parser.add_argument('log_file', help='Input .ekl filename')
    parser.add_argument('seq_file', help='Input .seq filename')
    parser.add_argument('find_key', nargs='?', help='Search key')
    parser.add_argument('find_value', nargs='?', help='Search value')

    # A few command line switches depend on yaml. We enable those only if we
    # could actually import yaml.
    if 'yaml' in sys.modules:
        parser.add_argument(
            '--config', help='Input .yaml configuration filename')
        parser.add_argument('--yaml', help='Output .yaml filename')
        parser.add_argument(
            '--template', help='Output .yaml config template filename')

    args = parser.parse_args()

    logging.basicConfig(
        format='%(levelname)s %(funcName)s: %(message)s',
        level=logging.DEBUG if args.debug else logging.INFO)

    # Command line argument 1 is the ekl file to open. Command line argument 2
    # is the seq file to open. Read both and combine them into a single
    # cross_check database.
    cross_check = read_log_and_seq(args.log_file, args.seq_file)
    logging.debug('{} combined test(s)'.format(len(cross_check)))

    # Take configuration file into account. This can perform transformations on
    # the tests results.
    if 'config' in args and args.config is not None:
        use_config(cross_check, args.config)

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
    s = map(
        lambda k: '{} {}(s)'.format(len(bins[k]), k.lower()),
        sorted(res_keys))

    logging.info(', '.join(s))

    # generate MD summary
    logging.debug(f'Generate {args.md}')

    with open(args.md, 'w') as resultfile:
        resultfile.write("# SCT Summary \n\n")
        resultfile.write("|  |  |\n")
        resultfile.write("|--|--|\n")

        # Loop on all the result values we found for the summary
        for k in sorted(res_keys):
            resultfile.write(
                "|{}:|{}|\n".format(k.title(), len(bins[k])))

        resultfile.write("\n\n")

        # Loop on all the result values we found (except PASS) for the sections
        # listing the tests by group
        n = 1
        res_keys_np = set(res_keys)
        res_keys_np.remove('PASS')

        for k in sorted(res_keys_np):
            resultfile.write("## {}. {} by group\n\n".format(n, k.title()))
            key_tree_2_md(bins[k], resultfile)
            n += 1

    # Generate yaml config template if requested
    if 'template' in args and args.template is not None:
        gen_template(cross_check, args.template)

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

    # Generate yaml if requested
    if 'yaml' in args and args.yaml is not None:
        gen_yaml(cross_check, args.yaml)

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
