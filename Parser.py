#SCT log parser


###Dict structure:
#tests = {
#    <guid> : test_dict 
#    <guid2> : test_dict2...
#}
#test_dict = {
#   "name": "some test",
#   "result": "pass/fail",
#   "group": "some group",
#   "test set": "some set",  
#   "sub set": "some subset",
#   "set guid": "XXXXXX",
#   "guid": "XXXXXX",
#   "comment": "some comment"
#   "log": "full log output"
#}


import sys

#based loosley on https://stackoverflow.com/a/4391978
# returns a filterd dict of dicts that meet some Key-value pair.
# I.E. key="result" value="FAILURE"
def key_value_find(dict1, key, value):
    found = {}
    for key2 in dict1:
        test = dict1[key2]
        if test[key] == value:
            found[key2]=test
    return found

#Were we intrept test logs into test dicts
def test_parser(string,current_group,current_test_set,current_set_guid,current_sub_set):
    test_dict = {
      "name": string[2], #FIXME:ACS just the name, SCT has name and Description. 
                         # ACS tests don't follow the same format as the rest of UEFI tests
      "result": string[1],
      "group": current_group,
      "test set": current_test_set,  
      "sub set": current_sub_set,
      "set guid": current_set_guid,
      "guid": string[0],
      #"comment": string[-1], #need to hash this out, sometime there is no comments
      "log": string
    }
    #FIXME:GUID's overlap... need fix, bad... 
    return test_dict["guid"], test_dict
    
#Parse the ekl file, and create a map of the tests
def ekl_parser (file):
    #create our "database" dict
    db_dict = dict()
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
        #i.e. 
        if split_line[0]=="HEAD":
            #split the header into test group and test set.
            current_group, current_set = split_line[8].split('\\')
            current_set_guid = split_line[4]
            current_sub_set = split_line[6]

        #FIXME: EKL file has a (in my opinion) bad line structure,
        # sometime we see a line that consits ' dump of GOP->I\n'
        #easiest way to skip is check for blank space in the first char
        elif split_line[0][0] != " ":
            #deliminiate on ':' for tests
            split_test = [new_string for old_string in split_line for new_string in old_string.split(':')]
            #put the test into a dict, and then place that dict in another dict with GUID as key
            guid,tmp_dict = test_parser(split_test,current_group,current_set,current_set_guid,current_sub_set)
            db_dict[guid]=tmp_dict

    return db_dict

def seq_parser(file):
    db_dict = dict()
    lines=file.readlines()
    #a test in a seq file is 7 lines, if not mod7, something wrong..
    magic=7
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
    #Command line argument 1, file to open, else open sample
    file = sys.argv[2] if len(sys.argv) >= 2 else "sample.ekl"
    db = {}
    #files are encoded in utf-16
    with open(file,"r",encoding="utf-16") as f:
        db = ekl_parser(f.readlines())
    
    #command line argument 2&3, key and value to find.
    find_key = sys.argv[3]  if len(sys.argv) >= 4 else "result"
    find_value = sys.argv[4] if len(sys.argv) >= 4 else "WARNING"    
    
    #if default search for Warnings
    found = key_value_find(db,find_key,find_value)
    
    #if default, also search for failures
    if len(sys.argv) < 4:
        found = {**found, **key_value_find(db,"result","FAILURE")}
    
    #print the dict
    print("found:",len(found),"items with search constraints")
    for x in found:
        print(found[x]["result"],":",found[x]["name"])

    #FIXME: needs to add support for custom seq name.
    if len(sys.argv) >= 4:
        return
    #seq file
    file2 = "sample.seq"
    db2 = {}
    #files are encoded in utf-16
    with open(file2,"r",encoding="utf-16") as f:
        db2 = seq_parser(f)
    
    cross_check_dict = dict()
    for x in db2:
        temp_dict = key_value_find(found,"set guid",x)
        if bool(temp_dict):
            cross_check_dict = {**cross_check_dict, **temp_dict}

    print()
    print("previous list filtered")
    for x in cross_check_dict:
        print(cross_check_dict[x]["result"],":",cross_check_dict[x]["name"])

    for x in db2:
        temp_dict = key_value_find(db, "set guid", x)
        if not (temp_dict):
            print("test set",db2[x]["name"],"was not found, possible silent drop")
        
    
main()
