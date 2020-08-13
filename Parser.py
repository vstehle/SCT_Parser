#SCT log parser


###Dict structure:
#tests = {
#    <guid> : test_dict 
#    <guid2> : test_dict2...
#}
#test_dict = {
#   "name": "some test",
#   "result": "pass/fail",
#   "test set": "some set",  
#   "group": "some group",
#   "guid": "XXXXXX",
#   "comment": "some comment"
#   "log": "full log output"
#}

#based loosley on https://stackoverflow.com/a/4391978
# returns a filterd dict of dicts that meet some Key-value pair.
# I.E. key="result" value="FAILURE"
def find(group, key, value):
    found = {}
    for guid in group:
        test = group[guid]
        if test[key] == value:
            found[guid]=test
    return found

#Were we intrept test logs into test dicts
def test_parser(string,current_group ="N/A",current_test_set="N/A"):
    test_dict = {
      "name": string[2], #FIXME:ACS just the name, SCT has name and Description. 
                         # ACS tests don't follow the same format as the rest of UEFI tests
      "result": string[1],
      "test set": current_test_set,  
      "group": current_group,
      "guid": string[0],
      #"comment": string[-1], #need to hash this out, sometime there is no comments
      "log": string
    }
    
    return test_dict["guid"], test_dict
    

def ekl_parser (file):
    #create our "database" dict
    db_dict = dict()

    current_group = "N/A"
    current_set = "N/A"

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

        #FIXME: EKL file has a (in my opinion) bad line structure,
        # sometime we see a line that consits ' dump of GOP->I\n'
        #easiest way to skip is check for blank space in the first char
        elif split_line[0][0] != " ":
            #deliminiate on ':' for tests
            split_test = [new_string for old_string in split_line for new_string in old_string.split(':')]
            guid,tmp_dict = test_parser(split_test,current_group,current_set)
            db_dict[guid]=tmp_dict

    return db_dict


def main():
    with open("sample.ekl","r",encoding="utf-16") as f:
        db = ekl_parser(f.readlines())
        #print the final dict,
        print(db)
        #print entries
        print(len(db))
        
        #find all passing tests,
        passes = find(db,"result","PASS")
        #print the dict
        print(passes)
       # print number of passing
        print(len(passes))
    

main()