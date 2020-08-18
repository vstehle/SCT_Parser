# SCT_Parser
---
This is an external Parser script for UEFI SCT & Arm ACS test suite.

It's designed to read a `.ekl` result log named `sample.ekl` and a generated `.seq` file named `sample.seq` from UEFI SCT configurator.
It will proceed to list the names of each test that has failed or had a warning, then filter that list based one the tests that were supposed to run according to the `.seq` file, including mentioning tests that would not run.


##Command line arguments (WIP)
###Diffrent File:
if you choose to, you can pass command like arguments like so `python3 Parser.py <file.ekl>`. this will provide a different `.ekl` log to search (such as `summary.ekl`), but run the same find failure/warnings, and cross check with a seq file. 

###Custom search
The next two arguments MUST be included together and will only search and display files that met that constraint, no cross check. `python3 Parser.py <file.ekl> <search key> <search value>`









##Notes
###Known Issues:
Currently If a test with the same guid is re-run, it will squash any previous test. I.E. TPL -4/6/8...

###Need to test
would a concatenation of all `.ekl` logs work?

###Dict structure:
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
   "comment": "some comment"
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
}```