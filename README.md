# SCT_Parser

This is an external Parser script for UEFI SCT. (WIP)

It's designed to read a `.ekl` results log from an UEFI SCT run, and a generated `.seq` from UEFI SCT configurator.

It will proceed to generate a Markdown file listing number of failures, passes, each test from the sequence file set that was Silently dropped, and a list of all failures and warnings.


## Usage
Usage to generate a "result md" is such. `python3 parser.py <log_file.ekl> <seq_file.seq>` 
If you do no provided any command line arguments it will use `sample.ekl` and `sample.seq`.


### Custom search
For a custom Key:value search, the next two arguments *MUST be included together.* The program will search and display files that met that constraint, without the crosscheck, and display the names, guid, and key:value to the command line. `python3 Parser.py <file.ekl> <file.seq> <search key> <search value>`

you can use the `test_dict` below to see available keys. 







## Notes
### Known Issues:
* "comment" is currently not implemented, as formatting is not currently consistent, should reflect the comments from the test.
* some SCT tests have shared GUIDs,
* some lines in ekl file follow Different naming Conventions
* some tests in the sequence file are not strongly Associated with the test spec. 

### Documentation

It is possible to convert this `README.md` into `README.pdf` with pandoc using
`make doc`. See `make help`.

### TODO:
* double check concatenation of all `.ekl` logs, preliminary tests show small Divergence between them and `summary.ekl` found in `Overall` folder. Cat.sh will generate this file.
* look into large number of dropped tests.


### db structure:
```
tests = [
    test_dict,
    est_dict2...
]

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
