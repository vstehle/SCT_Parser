#SCT log parser

#BIGFIXME: need to Decide on Definite Structure, and do a deeper dive into how logs are represented.gi

import sys
import json
#import csv

#based loosley on https://stackoverflow.com/a/4391978
# returns a filtered dict of dicts that meet some Key-value pair.
# I.E. key="result" value="FAILURE"
#if tests ar in lists.
def key_value_find(dict1, key, value):
    #print(key)
    found = list()
    for test in dict1:
        if test[key] == value:
            found.append(test)
    return found
    
#if tests are in dicts.
#def key_value_find(dict1, key, value):
#    found = {}
#    for key2 in dict1:
#        test = dict1[key2]
#        if test[key] == value:
#            found[key2]=test
#    return found

#Were we intrept test logs into test dicts
def test_parser(string,current_group,current_test_set,current_set_guid,current_sub_set):
    test_dict = {
      "name": string[2], #FIXME:Sometimes, SCT has name and Description, 
      "result": string[1],
      "group": current_group,
      "test set": current_test_set,  
      "sub set": current_sub_set,
      "set guid": current_set_guid,
      "guid": string[0], #FIXME:GUID's overlap... need fix... 
      #"comment": string[-1], #FIXME:need to hash this out, sometime there is no comments
      "log":
    }
    return (test_dict["guid"]+test_dict["set guid"]), test_dict
    
#Parse the ekl file, and create a map of the tests
def ekl_parser (file):
    #create our "database" dict
    #db_dict = dict()
    db_dict = list()
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
            current_group, current_set = split_line[8].split('\\')
            current_set_guid = split_line[4]
            current_sub_set = split_line[6]

        #FIXME:? EKL file has an inconsistent line structure,
        # sometime we see a line that consits ' dump of GOP->I\n'
        #easiest way to skip is check for blank space in the first char
        elif split_line[0][0] != " ":
            #deliminiate on ':' for tests
            split_test = [new_string for old_string in split_line for new_string in old_string.split(':')]
            #put the test into a dict, and then place that dict in another dict with GUID as key
            guid,tmp_dict = test_parser(split_test,current_group,current_set,current_set_guid,current_sub_set)
            #print(guid)
            db_dict.append(tmp_dict)

    return db_dict

def seq_parser(file):
    db_dict = dict()
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
            db_dict[seq_dict["guid"]]=seq_dict #put in a dict based on guid

    return db_dict



def main():
    #Command line argument 1, ekl file to open, else open sample
    log_file = sys.argv[1] if len(sys.argv) >= 2 else "sample.ekl"
    db1 = {} #"database 1" all tests.
    with open(log_file,"r",encoding="utf-16") as f: #files are encoded in utf-16
        db1 = ekl_parser(f.readlines())

    #Command line argument 2, seq file to open, else open sample
    seq_file = sys.argv[2] if len(sys.argv) >= 3 else "sample.seq"
    db2 = {} #"database 2" all test sets that should run
    with open(seq_file,"r",encoding="utf-16") as f: #files are encoded in utf-16
        db2 = seq_parser(f)
    
    #cross check is filled only with tests labled as "run" int the seq file
    cross_check_dict = list()
    #cross_check_dict = list()
    #combine a list of test sets that did not run for whatever reason.
    would_not_run = list()
    #would_not_run = dict()
    for x in db2: #for each "set guid" in db2
        temp_dict = key_value_find(db1,"set guid",x)#find tests in db1 with given set guid
        if bool(temp_dict): #if its not empty, apprend it to our dict
            #list
            cross_check_dict = (cross_check_dict +temp_dict)
            #dict
            #cross_check_dict = {**cross_check_dict, **temp_dict}
        else: #if it is empty, this test set was not run.
            would_not_run.append(db2[x]) 

    
    #search for failures and warnings & passes,
    
    failures = key_value_find(cross_check_dict,"result","FAILURE")
    warnings = key_value_find(cross_check_dict,"result","WARNING")
    passes = key_value_find(cross_check_dict,"result","PASS")
    #list
    fail_and_warn = (failures + warnings)#dict of failures and warnings
    #dict
    #fail_and_warn = {**failures, **warnings}#dict of failures and warnings


    #FIXME:? Do we want CSV and MD. 
    # generate CSV summary
#    with open('result.csv', 'w') as csvfile:
#        result_writer = csv.writer(csvfile, delimiter=',')
#        result_writer.writerow(['']*9) 
#        result_writer.writerow(["Failures:",len(failures)])
#        result_writer.writerow(["Warnings:",len(warnings)])
#        result_writer.writerow(["Pass:",len(passes)])
#        result_writer.writerow(['']*9) 
#
#        #If there were any silently dropped, lets print them
#        if len(would_not_run) > 0:
#            result_writer.writerow(["Silently Dropped:"]) 
#            not_run_writer = csv.DictWriter(csvfile, would_not_run[0])
#            not_run_writer.writeheader()
#            for x in would_not_run:
#                not_run_writer.writerow(x)
#            result_writer.writerow(['']*9)
#        
#        #lets print every test that failed or had a wanring. if any did!
#        result_writer.writerow(["Fail & Warn tests:"]) 
#        first_guid = fail_and_warn[0]["guid"]
#        test_writer = csv.DictWriter(csvfile, fail_and_warn[first_guid])
#        test_writer.writeheader()
#        for x in fail_and_warn:
#            test_writer.writerow(fail_and_warn[x])


    # generate MD summary
    #TODO: this should be split out into functions, and also "Beautified"
    with open('result.md', 'w') as resultfile:
        resultfile.write("# SCT Summary \n")
        resultfile.write("### Failures:"+str(len(failures))+"\n")
        resultfile.write("### Warnings:"+str(len(warnings))+"\n")
        resultfile.write("### Passes:"+str(len(passes))+"\n")
        resultfile.write("### Dropped:"+str(len(would_not_run))+"\n")
        if len(would_not_run) > 0:
            resultfile.write("\n\n# Silently dropped or missing \n")
            resultfile.write("|dict| \n")
            resultfile.write("|---| \n")
            for x in would_not_run:
                resultfile.write("| ")
                json.dump(x,resultfile)
                resultfile.write(" |\n")
        if len(fail_and_warn) > 0:
            resultfile.write("\n# Failures & warnings\n")
            resultfile.write("|dict| \n")
            resultfile.write("|---| \n")
            for x in fail_and_warn:
                json.dump(x,resultfile)
                resultfile.write(" |\n")
    
    #command line argument 3&4, key are to support a key & value search.
    #these will be displayed in CLI
    if len(sys.argv) >= 5:
        find_key = sys.argv[3]
        find_value = sys.argv[4]
        found = key_value_find(db1,find_key,find_value)
        #print the dict
        print("found:",len(found),"items with search constraints")
        for x in found:
            print(found[x]["guid"],":",found[x]["name"],"with",found[x][find_key],":",found[x][find_value])

main()
