#!/bin/bash

# Flycheck creates temporary files that it sometimes doesn't clean up
# before testing.  Make sure they're gone so that neither black nor
# flake8 complain about them.
rm -fv flycheck_*.py

black --check --verbose --line-length 79 gc_accounts.py gc_ledger.py
flake8 --tee --output-file flake8.report gc_accounts.py gc_ledger.py

# Maybe could actually call tests here.
