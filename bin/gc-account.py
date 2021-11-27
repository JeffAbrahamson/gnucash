#!/usr/bin/env python3

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
    account_code = args.account
    account = book.get(piecash.Account, name=account_code)
    if len(account.children) > 0:
        print('This is not a leaf account.')
        return
    balance = 0.0
    table = []
    header = ['Date', 'Num', 'Descr', 'Dx', 'Cx', 'Solde']
    for split in account.splits:
        transaction = split.transaction
        value = float(split.quantity)
        if split.quantity < 0:
            dx = '{amt:10.2f}'.format(amt=split.quantity)
            cx = ''
        else:
            dx = ''
            cx = '{amt:10.2f}'.format(amt=split.quantity)
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
                if state != 'y' and state != 'v']) > 0:
            num += '[*]'
        descr = transaction.description[:40]
        table.append([date, num, descr, dx, cx, value])
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
