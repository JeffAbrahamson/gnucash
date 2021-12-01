#!/usr/bin/env python3

"""Print a French-style P&L report.

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
    parser.add_argument('--begin', required=False,
                        type=datetime.date.fromisoformat,
                        default=datetime.date(datetime.date.today().year, 1, 1),
                        help='Beginning of accounting period')
    parser.add_argument('--end', required=False,
                        type=datetime.date.fromisoformat,
                        default=datetime.date(datetime.date.today().year, 12, 31),
                        help='End of accounting period')
    args = parser.parse_args()
    book = piecash.open_book(args.gnucash,
                             readonly=True,
                             open_if_lock=True)
    print("Éléments pour compte de résultats du {begin} au {end}".format(
        begin=args.begin, end=args.end))
    balances = get_income_expenses(book, args.begin, args.end)
    print('\nDépenses:')
    print(tabulate([[k, v] for k, v in balances['6'].items()],
                   ['Compte', 'Montant'], 'fancy_grid'))
    print("Total : {s}".format(
        s=sum([v for k, v in balances['6'].items()])))
    print('\nRevenu:')
    print(tabulate([[k, v] for k, v in balances['7'].items()],
                   ['Compte', 'Montant'], 'fancy_grid'))
    print("Total : {s}".format(
        s=sum([v for k, v in balances['7'].items()])))

    print("\nEmploi des contributions volontaires en nature :")
    print(tabulate([[k, v] for k, v in balances['86'].items()],
                   ['Compte', 'Montant'], 'fancy_grid'))
    print("\nContributions volontaires en nature :")
    print(tabulate([[k, v] for k, v in balances['87'].items()],
                   ['Compte', 'Montant'], 'fancy_grid'))

def get_income_expenses(book, begin_date, end_date):
    """Return a dict of dicts (income and expenses) for all transactions
    within the inclusive date range provided by begin and end.  The
    sub-dicts map account name to sum of entries during the date
    range.

    """
    balances = {'6': {}, '7': {}, '86': {}, '87': {}}
    for account in book.accounts:
        account_prefix = account.name[0]
        if account_prefix in ('6', '7', '8'):
            if '8' == account_prefix:
                account_prefix = account.name[0:2]
            balance = 0
            for split in account.splits:
                if begin_date <= split.transaction.post_date and \
                   end_date >= split.transaction.post_date:
                    balance += split.quantity
            if balance != 0:
                if account_prefix in ('7', '86'):
                    balance = -balance
                balances[account_prefix][account.name] = balance
    return balances

    #     for entry in account:
    #         entry.transaction.post_date
    #         entry.is_debit
    #         entry.is_credit
    #         entry.value
    # return None, None


if __name__ == '__main__':
    main()
