#!/bin/bash

# Config.
work_dir="$HOME/work/financial/"
gnucash_file="$HOME/work/finance/gnucash/current/compta-perso.gnucash"

cd "$work_dir"
. venv/bin/activate
piecash ledger "$gnucash_file" --output ledger.out

fin-account-list.py --gnucash "$gnucash_file" --outfile accounts.txt
