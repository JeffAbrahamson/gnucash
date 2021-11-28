#!/usr/bin/env python3

"""Print a French-style balance sheet.

J'ai fait ce script à l'origine pour mon usage dans une petite
association dont les besoins sont plutôt faibles.  D'ailleurs, il me
semble inévitable qu'on serait obligé de passer à un logiciel plus
adapté aux interactions avec les collectivités.  Aussi, je me contente
à fournir les chiffres nécessaires à copier-coller dans les CERFA.

"""

import argparse
import datetime
import os
import piecash
from tabulate import tabulate

def main():
    """Do what we do."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--gnucash', type=str, required=False,
                        default=os.getenv('_gc__default_filename'),
                        help='filename containing sqlite3 gnucash file')
    parser.add_argument('--end', type=datetime.date, required=False,
                        default=datetime.date(datetime.date.today().year, 12, 31),
                        help='End of accounting period')
    args = parser.parse_args()
    book = piecash.open_book(args.gnucash,
                             readonly=True,
                             open_if_lock=True)
    print("Éléments pour bilan daté {end}".format(end=args.end))
    balances = get_balances(book, args.end)
    print('\nBilan:')
    print(tabulate([[k, v] for k, v in balances.items()],
                   ['Compte', 'Montant'], 'fancy_grid'))

def get_balances(book, end_date):
    """Return two dicts (income and expenses) for all transactions within
    the inclusive date range provided by begin and end.  The dicts map
    account name to sum of entries during the date range.

    """
    balances = {}
    for account in book.accounts:
        account_prefix = account.name[0]
        if account_prefix not in ('6', '7', '8'):
            balance = 0
            for split in account.splits:
                if end_date >= split.transaction.post_date:
                    balance += split.quantity
            if balance != 0:
                balances[account.name] = balance
    return balances

if __name__ == '__main__':
    main()
