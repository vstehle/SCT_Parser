#SCT log parser

#https://stackoverflow.com/a/4391978
def find(lst, key, value):
    for i, dic in enumerate(lst):
        if dic[key] == value:
            return i
    return -1

#Were we intrept test logs into test dicts
def test_parser(string,current_group ="N/A",current_test_set="N/A"):
    print(string)
    #test_dict = {
    #   "name": "some test",
    #   "result": "pass",
    #   "test set": "some set",  
    #   "group": "some group",
    #   "guid": "XXXXXX",
    #    "comment": "some comment"
    #   "log": "log output"
    #}
    pass
    

def ekl_parser (file):
    #create our "database" dict
    db_dict = dict()

    current_group = "N/A"
    current_set = "N/A"

    for line in file:
        #strip the line of | & || used for sepration
        split_line = [string for string in line.split('|') if string != ""]
        #print(split_line)

        #TODO:I can skip TERM, but I feel like "\n" should be able to be handled in the above list comprehension 
        if split_line[0]=="TERM" or split_line[0]=="\n":
            continue

        #The "HEAD" tag is the only indcation we are on a new test set
        if split_line[0]=="HEAD":
            #split the header into test group and test set.
            current_group, current_set = split_line[8].split('\\')
            print("group:",current_group,"set:",current_set)
            #print(split_line)

        #FIXME: EKL file has a (in my opinion) bad line structure,
        # sometime we see a line that consits ' dump of GOP->I\n'
        #easiest way to skip is check for blank space in the first char
        elif split_line[0][0] != " ":
            
            split_test = [new_string for old_string in split_line for new_string in old_string.split(':')]
            #print(split_test)
            print("test:",split_test[2])
            print(split_line[0],split_line[1])

    return db_dict


def main():
    with open("SCT/Overall/Summary.ekl","r",encoding="utf-16") as f:
        ekl_parser(f.readlines())
   
    

main()