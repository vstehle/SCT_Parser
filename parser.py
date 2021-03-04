#!/usr/bin/env python3
#SCT log parser


import sys
import argparse
import csv
import logging
import json


#based loosley on https://stackoverflow.com/a/4391978
# returns a filtered dict of dicts that meet some Key-value pair.
# I.E. key="result" value="FAILURE"
def key_value_find(list_1, key, value):
    found = list()
    for test in list_1:
        if test[key] == value:
            found.append(test)
    return found


#Were we intrept test logs into test dicts
def test_parser(string, current):
    test_list = {
      "name": string[2], #FIXME:Sometimes, SCT has name and Description,
      "result": string[1],
      **current,
      "guid": string[0], #FIXME:GUID's overlap
      #"comment": string[-1], #FIXME:need to hash this out, sometime there is no comments
      "log": ' '.join(string[3:])
    }
    return test_list

#Parse the ekl file, and create a map of the tests
def ekl_parser (file):
    #create our "database" dict
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

        #FIXME:? EKL file has an inconsistent line structure,
        # sometime we see a line that consits ' dump of GOP->I\n'
        #easiest way to skip is check for blank space in the first char
        elif split_line[0] != '' and split_line[0][0] != " ":
            try:
                #deliminiate on ':' for tests
                split_test = [new_string for old_string in split_line for new_string in old_string.split(':')]
                #put the test into a dict, and then place that dict in another dict with GUID as key
                tmp_dict = test_parser(split_test, current)
                temp_list.append(tmp_dict)
                n += 1
            except:
                print("Line:",split_line)
                sys.exit("your log may be corrupted")
        else:
            logging.error(f"Unparsed line {i} `{line}'")

    if s:
        logging.debug(f'{s} skipped test set(s)')

    return temp_list

#Parse Seq file, used to tell which tests should run.
def seq_parser(file):
    temp_dict = list()
    lines=file.readlines()
    magic=7 #a test in a seq file is 7 lines, if not mod7, something wrong..
    if len(lines)%magic != 0:
        sys.exit("seqfile cut short, should be mod7")
    #the utf-16 char makes this looping a bit harder, so we use x+(i) where i is next 0-6th
    for x in range(0,len(lines),magic): #loop ever "7 lines"
        #(x+0)[Test Case]
        #(x+1)Revision=0x10000
        #(x+2)Guid=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
        #(x+3)Name=InstallAcpiTableFunction
        #(x+4)Order=0xFFFFFFFF
        #(x+5)Iterations=0xFFFFFFFF
        #(x+6)(utf-16 char)
        #currently only add tests that are supposed to run, should add all?
        #0xFFFFFFFF in "Iterations" means the test is NOT supposed to run
        if not "0xFFFFFFFF" in lines[x+5]:
            seq_dict = {
                "name": lines[x+3][5:-1],#from after "Name=" to end (5char long)
                "guid": lines[x+2][5:-1],#from after"Guid=" to the end, (5char long)
                "Iteration": lines[x+5][11:-1],#from after "Iterations=" (11char long)
                "rev": lines[x+1][9:-1],#from after "Revision=" (9char long)
                "Order": lines[x+4][6:-1]#from after "Order=" (6char long)
            }
            temp_dict.append(seq_dict) #put in a dict based on guid

    return temp_dict

#group items by key, and print by key
#we slowly iterate through the list, group and print groups
def key_tree_2_md(input_list,file,key):
    #make a copy so we don't destroy the first list.
    temp_list = input_list.copy()
    while temp_list:
        test_dict = temp_list.pop()
        found, not_found = [test_dict],[]
        #go through whole list looking for key match
        while temp_list:
            next_dict = temp_list.pop()
            if next_dict[key] == test_dict[key]: #if match add to found
                found.append(next_dict)
            else: #else not found
                not_found.append(next_dict)
        temp_list = not_found #start over with found items removed
        file.write("### " + test_dict[key])
        dict_2_md(found,file)



#generic writer, takes a list of dicts and turns the dicts into an MD table.
def dict_2_md(input_list,file):
    if len(input_list) > 0:
        file.write("\n\n")
        #create header for MD table using dict keys
        temp_string1, temp_string2 = "|", "|"
        for x in (input_list[0].keys()):
            temp_string1 += (x + "|")
            temp_string2 += ("---|")
        file.write(temp_string1+"\n"+temp_string2+"\n")
        #print each item from the dict into the table
        for x in input_list:
            test_string = "|"
            for y in x.keys():
                test_string += (x[y] + "|")
            file.write(test_string+'\n')
    #seprate table from other items in MD
    file.write("\n\n")


# Sort tests data in-place
# sort_keys is a comma-separated list
# The first key has precedence, then the second, etc.
# To use python list in-place sorting, we use the keys in reverse order.
def sort_data(cross_check, sort_keys):
    logging.debug(f"Sorting on `{sort_keys}'")
    for k in reversed(sort_keys.split(',')):
        cross_check.sort(key=lambda x: x[k])


# Generate csv
def gen_csv(cross_check, filename):
    # Find keys
    keys = set()

    for x in cross_check:
        keys = keys.union(x.keys())

    # Write csv
    logging.debug(f'Generate {filename}')

    with open(filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(
            csvfile, fieldnames=sorted(keys), delimiter=';')
        writer.writeheader()
        writer.writerows(cross_check)


# Generate json
def gen_json(cross_check, filename):
    logging.debug(f'Generate {filename}')

    with open(filename, 'w') as jsonfile:
        json.dump(cross_check, jsonfile, sort_keys=True, indent=2)


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


def main():
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
    parser.add_argument(
        'log_file', nargs='?', default='sample.ekl',
        help='Input .ekl filename')
    parser.add_argument(
        'seq_file', nargs='?', default='sample.seq',
        help='Input .seq filename')
    parser.add_argument('find_key', nargs='?', help='Search key')
    parser.add_argument('find_value', nargs='?', help='Search value')
    args = parser.parse_args()

    logging.basicConfig(
        format='%(levelname)s %(funcName)s: %(message)s',
        level=logging.DEBUG if args.debug else logging.INFO)

    #Command line argument 1, ekl file to open
    db1 = list() #"database 1" all tests.
    logging.debug(f'Read {args.log_file}')

    with open(args.log_file,"r",encoding="utf-16") as f: #files are encoded in utf-16
        db1 = ekl_parser(f.readlines())

    logging.debug('{} test(s)'.format(len(db1)))

    #Command line argument 2, seq file to open
    db2 = dict() #"database 2" all test sets that should run
    logging.debug(f'Read {args.seq_file}')

    with open(args.seq_file,"r",encoding="utf-16") as f: #files are encoded in utf-16
        db2 = seq_parser(f)

    logging.debug('{} test set(s)'.format(len(db2)))

    # Produce a single cross_check database from our two db1 and db2 databases.
    cross_check = combine_dbs(db1, db2)


    # Sort tests data in-place, if requested
    if args.sort is not None:
        sort_data(cross_check, args.sort)

    # search for failures, warnings, passes & others
    # We detect all present keys in additions to the expected ones. This is
    # handy with config rules overriding the result field with arbitrary values.
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
            key_tree_2_md(bins[k], resultfile, "group")
            n += 1

    # Generate csv if requested
    if args.csv is not None:
        gen_csv(cross_check, args.csv)

    # Generate json if requested
    if args.json is not None:
        gen_json(cross_check, args.json)

    #command line argument 3&4, key are to support a key & value search.
    #these will be displayed in CLI
    if args.find_key is not None and args.find_value is not None:
        found = key_value_find(db1, args.find_key, args.find_value)
        #print the dict
        print("found:",len(found),"items with search constraints")
        for x in found:
            print(
                x["guid"], ":", x["name"], "with", args.find_key, ":",
                x[args.find_key])


main()
