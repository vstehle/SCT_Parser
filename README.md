# SCT_Parser
---
This is an external Parser script for UEFI SCT. (Arm ACS test suite WIP)

It's designed to read a `.ekl` results log (default is `sample.ekl`), and a generated `.seq` (default is `sample.seq`) from UEFI SCT configurator.

It will proceed to generate a CSV listing fails, passes, and each test set that was Silent dropped, and a list of all failed and warnings.


## Command line arguments (WIP)

### Different File:
if you choose to, you can pass command like arguments like so `python3 Parser.py <file.ekl> <file.seq>` This will provide a different `.ekl` log to search (such as `summary.ekl`), and a different `.seq` file, (such as `seq.seq`) 



### Custom search
For a custom Key:value search, the next two arguments *MUST be included together.* The program will search and display files that met that constraint, without the crosscheck, and display the names, guid, and key:value to the command line. `python3 Parser.py <file.ekl> <file.seq> <search key> <search value>`

you can use the `test_dict` below to see available keys. 









## Notes
### Known Issues:
* "comment" is currently not implemented, as formatting is not currently consistent, should reflect the comments from the test.
* Currently ACS tests have shared GUIDs
* ACS follows different naming convention

### Need to test
would a concatenation of all `.ekl` logs work?

### Dict structure:
```
tests = {
    <guid> : test_dict 
    <guid2> : test_dict2...
}

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