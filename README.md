# Gnucash scripts

These are various scripts and resources to make interacting with
gnucash more efficient and more pleasant for me.

A few setup scripts are bash, the rest are python, making use of the
piecash library to access gnucash files in sqlite3 format.

The requirements.txt file lists the required python modules to
install.  The intent is that one uses the bash function gc-use to
specify the current gnucash file to use for these scripts, and the
scripts should all respect that decision.  The gc-use function sources
bin/gc-activate.sh, which sets up appropriate environment variables.

The setup in gc-activate.sh is quite specific to my own use, which is
an obvious opportunity for improvement.

This is all a bit in flux.


VISION:

I think I want two programs:

  * gc_accounts.py
    - output set of account names
    - with args are filters (grep-style)
    - with -E, -F, -v, -G, -i as grep
    - --leaf-only (default: false)
    - --show-tree (default: false)
  * gc_ledger.py
    - output the general ledger
    - --begin (date or day offset; default: today - 30)
    - --end   (date or day offset; default: today)
    - --account  (comma-separated list of accounts to match)
    - --format (single-line, double-line, full; default: single-line)

and a few aliases:

  * gc-a for gc_accounts.py
  * gc-l for gc_ledger.py
  * gc-ar for gc_ledger restricted to accounts receivable
  * gc-ap for gc_ledger restricted to accounts payable
  * gc-expenses for gc_ledger restricted to expense accounts
  * gc-income for gc_ledger restricted to income accounts


TODO:

  * only activate venv if it exists, otherwise use global
  * can I ditch ledger, it is a preprocessing step I'd rather not have to remember
  * the programs here are far from intuitive
  * this needs far better documentation, I have trouble remembering what things mean
  * gc-use isn't defined here
  * gc-use can be simplified a bit, I think it only need specify the gc filename

${_gc__default_filename} --> The gnucash file to use

I think these two just point to a text file of accounts exported via
ledger.  This should be replaced with a simple python script that
extracts accounts as needed.

${_gc__cache}            --> The cache directory, perhaps ledger-related?
${_gc__default_index}    --> The cache filename, perhaps ledger-related?
