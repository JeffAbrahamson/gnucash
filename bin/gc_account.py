#!/usr/bin/env python3

"""
Print an extract of a single account.
"""

import argparse
import os
import piecash
from tabulate import tabulate

def main():
    """Do what we do."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--gnucash', type=str, required=False,
                        default=os.getenv('_gc__default_filename'),
                        help='filename containing sqlite3 gnucash file')
    parser.add_argument('--account', type=str, required=True,
                        help='Name of account')
    args = parser.parse_args()
    book = piecash.open_book(args.gnucash,
                             readonly=True,
                             open_if_lock=True)
    account = book.get(piecash.Account, name=args.account)
    print_account(account)

def print_account(account):
    """Pretty-print the requested account.
    """
    if len(account.children) > 0:
        print('This is not a leaf account.')
        return
    table = []
    header = ['Date', 'Num', 'Descr', 'Dx', 'Cx', 'Solde']
    for split in account.splits:
        transaction = split.transaction
        value = split.quantity
        if split.quantity > 0:
            debit_x = '{amt:10.2f}'.format(amt=split.quantity)
            credit_x = ''
        else:
            debit_x = ''
            credit_x = '{amt:10.2f}'.format(amt=-split.quantity)
        date = transaction.post_date
        num = transaction.num
        # If this transaction has a portion against a bank
        # account and that portion is not yet reconciled,
        # indicate that with an '*'.
        bank_reconcile_state =  [x.reconcile_state
                                 for x
                                 in transaction.splits
                                 if x.account.name.startswith('512')]
        if len([state for state in bank_reconcile_state
                if state not in ('y', 'v')]) > 0:
            num += '[*]'
        descr = transaction.description[:40]
        table.append([date, num, descr, debit_x, credit_x, value])
    table.sort(key=lambda x: x[0])
    bal = 0
    for row in table:
        bal += row[5]
        row[5] = bal
    print(tabulate(table, header, 'fancy_grid'))

    # Also available:
    #   split.transaction.notes

if __name__ == '__main__':
    main()
