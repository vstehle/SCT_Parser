#!/usr/bin/env python3
#SCT log parser


import sys

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
def test_parser(string,current_group,current_test_set,current_set_guid,current_sub_set):
    test_list = {
      "name": string[2], #FIXME:Sometimes, SCT has name and Description,
      "result": string[1],
      "group": current_group,
      "test set": current_test_set,
      "sub set": current_sub_set,
      "set guid": current_set_guid,
      "guid": string[0], #FIXME:GUID's overlap
      #"comment": string[-1], #FIXME:need to hash this out, sometime there is no comments
      "log": ' '.join(string)
    }
    return test_list

#Parse the ekl file, and create a map of the tests
def ekl_parser (file):
    #create our "database" dict
    temp_list = list()
    #All tests are grouped by the "HEAD" line the procedes them.
    current_group = "N/A"
    current_set = "N/A"
    current_set_guid = "N/A"
    current_sub_set = "N/A"

    for line in file:
        #strip the line of | & || used for sepration
        split_line = [string for string in line.split('|') if string != ""]

        #TODO:I can skip TERM, but I feel like "\n" should be able to be handled in the above list comprehension
        if split_line[0]=="TERM" or split_line[0]=="\n":
            continue

        #The "HEAD" tag is the only indcation we are on a new test set
        if split_line[0]=="HEAD":
            #split the header into test group and test set.
            try:
                current_group, current_set = split_line[8].split('\\')
            except:
                current_group, current_set =split_line[8],split_line
            current_set_guid = split_line[4]
            current_sub_set = split_line[6]

        #FIXME:? EKL file has an inconsistent line structure,
        # sometime we see a line that consits ' dump of GOP->I\n'
        #easiest way to skip is check for blank space in the first char
        elif split_line[0][0] != " ":
            try:
                #deliminiate on ':' for tests
                split_test = [new_string for old_string in split_line for new_string in old_string.split(':')]
                #put the test into a dict, and then place that dict in another dict with GUID as key
                tmp_dict = test_parser(split_test,current_group,current_set,current_set_guid,current_sub_set)
                temp_list.append(tmp_dict)
            except:
                print("Line:",split_line)
                sys.exit("your log may be corrupted")
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


def main():
    #Command line argument 1, ekl file to open, else open sample
    log_file = sys.argv[1] if len(sys.argv) >= 2 else "sample.ekl"
    db1 = list() #"database 1" all tests.
    with open(log_file,"r",encoding="utf-16") as f: #files are encoded in utf-16
        db1 = ekl_parser(f.readlines())

    #Command line argument 2, seq file to open, else open sample
    seq_file = sys.argv[2] if len(sys.argv) >= 3 else "sample.seq"
    db2 = dict() #"database 2" all test sets that should run
    with open(seq_file,"r",encoding="utf-16") as f: #files are encoded in utf-16
        db2 = seq_parser(f)

    #cross check is filled only with tests labled as "run" int the seq file
    cross_check = list()
    #combine a list of test sets that did not run for whatever reason.
    would_not_run = list()
    for x in db2: #for each "set guid" in db2
        temp_dict = key_value_find(db1,"set guid",x["guid"])#find tests in db1 with given set guid
        if bool(temp_dict): #if its not empty, apprend it to our dict
            cross_check = (cross_check +temp_dict)
        else: #if it is empty, this test set was not run.
            would_not_run.append(x)


    #search for failures and warnings & passes,

    failures = key_value_find(cross_check,"result","FAILURE")
    warnings = key_value_find(cross_check,"result","WARNING")
    passes = key_value_find(cross_check,"result","PASS")


    # generate MD summary
    with open('result.md', 'w') as resultfile:
        resultfile.write("# SCT Summary \n")
        resultfile.write("### 1. Dropped: "+str(len(would_not_run))+"\n")
        resultfile.write("### 2. Failures: "+str(len(failures))+"\n")
        resultfile.write("### 3. Warnings: "+str(len(warnings))+"\n")
        resultfile.write("### 4. Passes: "+str(len(passes))+"\n")
        resultfile.write("\n\n")

        resultfile.write("## 1. Silently dropped or missing")
        dict_2_md(would_not_run,resultfile)

        resultfile.write("## 4. Failure by group")
        resultfile.write("\n\n")
        key_tree_2_md(failures,resultfile,"group")


        resultfile.write("## 3. Warnings by group")
        resultfile.write("\n\n")
        key_tree_2_md(warnings,resultfile,"group")


    #command line argument 3&4, key are to support a key & value search.
    #these will be displayed in CLI
    if len(sys.argv) >= 5:
        find_key = sys.argv[3]
        find_value = sys.argv[4]
        found = key_value_find(db1,find_key,find_value)
        #print the dict
        print("found:",len(found),"items with search constraints")
        for x in found:
            print(x["guid"],":",x["name"],"with",find_key,":",x[find_key])

main()
