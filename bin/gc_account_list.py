#!/usr/bin/env python3

"""Export a greppable text file of the flattened account hierarchy.
"""

import argparse
import os.path
import piecash

def main():
    """Do what we do."""
    parser = argparse.ArgumentParser()
    parser.add_argument('-g', '--gnucash', type=str, required=False,
                        help='Filename containing sqlite3 gnucash file or index into accounts map')
    parser.add_argument('-o', '--outfile', type=str, required=False,
                        help='Filename for account list')
    args = parser.parse_args()
    if args.gnucash is None:
        args.gnucash=os.getenv('_gc__default_filename')
    if args.outfile is None:
        args.outfile=os.getenv('_gc__cache') + '/' + os.getenv('_gc__default_index')

    if os.path.exists(args.gnucash):
        book_filename = args.gnucash
    else:
        book_filename = os.getenv('_gc__' + args.gnucash)
    book = piecash.open_book(book_filename,
                             readonly=True,
                             open_if_lock=True)
    with open(args.outfile, 'w') as fp_out:
        for account in book.accounts:
            fp_out.write(('{n}  ({d})\n'.format(n=account.name, d=account.description)))

if __name__ == '__main__':
    main()
