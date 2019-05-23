#!/usr/bin/env python

"""Export a greppable text file of the flattened account hierarchy.
"""

import argparse
import piecash

def main():
    """Do what we do."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--gnucash', type=str, required=True,
                        help='filename containing sqlite3 gnucash file')
    parser.add_argument('--outfile', type=str, required=True,
                        help='filename of output tex/pdf')
    args = parser.parse_args()
    book = piecash.open_book(args.gnucash,
                             readonly=True,
                             open_if_lock=True)
    with open(args.outfile, 'w') as fp_out:
        for account in book.accounts:
            fp.write(('{n}  ({d})\n'.format(n=account.name, d=account.description)))

if __name__ == '__main__':
    main()
