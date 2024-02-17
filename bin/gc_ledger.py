#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""Print a General Ledger report from a GnuCash database.

Options permit filtering by account, date, and transaction text.

"""

import os
import argparse
import datetime
import re
from tabulate import tabulate
import piecash


GPL = """
Copyright 2024  Jeff Abrahamson

This file is part of gc_ledger.py.

gc_ledger.py is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

gc_ledger.py is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with gc_ledger.py.  If not, see <http://www.gnu.org/licenses/>.
"""


def parse_date_or_offset(input_str):
    """Parse a date string or a day offset.

    For example, "-5d" for 5 days ago.

    This surely could benefit from a more robust parser or even using
    a library like dateutil or dateutil.parser.

    """
    if re.match(r"^-?\d+d$", input_str):
        days = int(input_str[:-1])
        return datetime.date.today() + datetime.timedelta(days=days)
    return datetime.datetime.strptime(input_str, "%Y-%m-%d").date()


def filter_accounts(book, accounts, verbose):
    """Return a list of accounts matching a list of regexes.

    The argument accounts is a list of regular expressions.

    TODO: Verify that all accounts are the same type so that the union
    makes sense.

    """
    if accounts:
        accounts_regex = re.compile("|".join(accounts))
        filtered_account = [
            a for a in book.accounts if accounts_regex.search(a.fullname)
        ]
        if verbose:
            # print(f"Accounts: {filtered_accounts}")
            print(f"Found {len(filtered_account)} matching accounts.")
        return filtered_account
    print("No accounts specified, using all accounts.")
    return book.accounts


def filter_splits_by_date(begin_date, end_date, accounts, verbose):
    """Return a list of splits within a date range.

    Return those splits in the given accounts whose post date is
    within the date range (inclusive).

    """
    splits = []
    for account in accounts:
        these_splits = [
            split
            for split in account.splits
            if begin_date <= split.transaction.post_date <= end_date
        ]
        splits += these_splits
    if verbose:
        print(f"Found {len(splits)} matching splits.")
    return splits


def filter_transactions(splits, filters, flags, verbose):
    """Apply grep-style filters to transaction splits"""
    if not filters:
        if verbose:
            print("No filters specified, using all transactions.")
        return splits
    if verbose:
        print(
            f"Applying {len(filters)} filters to {len(splits)} transactions: {filters}."
        )
    filtered_splits = [
        split
        for split in splits
        if any(
            (
                split.transaction.description is not None
                and re.search(one_filter, split.transaction.description, flags)
            )
            or (
                split.transaction.notes is not None
                and re.search(one_filter, split.transaction.notes, flags)
            )
            or (
                split.memo is not None
                and re.search(one_filter, split.memo, flags)
            )
            for one_filter in filters
        )
    ]
    if verbose:
        print(f"Found {len(filtered_splits)} matching transactions.")
    return filtered_splits


def print_splits_full(splits):
    """Print a list of splits with full split detail.

    We want to show the opposing accounts here.

    """
    print("Full split detail is not yet implemented.")
    return


def amount_with_currency(amount, currency, sign):
    amount *= sign
    if currency == "USD":
        return f"${amount:.2f}"
    if currency == "EUR":
        return f"€{amount:.2f}"
    if currency == "GBP":
        return f"£{amount:.2f}"
    return f"{amount:.2f} {currency}"


def print_splits(splits, format):
    """Print a list of splits in a specified format."""
    if format == "full":
        print_splits_full(splits)
        return
    rows = []
    for split in splits:
        rows.append(
            {
                "date": split.transaction.post_date,
                "description": split.transaction.description,
                "notes": split.transaction.notes,
                "memo": split.memo,
                "account": split.account.name,
                "value": split.value,
                "quantity": split.quantity,
                "currency": split.account.commodity.mnemonic,
            }
        )

    colalign = ("left", "left", "right", "right")
    if format == "single-line":
        display_rows = [
            (
                entry["date"],
                entry["description"],
                amount_with_currency(entry["value"], entry["currency"], 1)
                if split.is_debit
                else "",
                amount_with_currency(entry["value"], entry["currency"], -1)
                if split.is_credit
                else "",
            )
            for entry in rows
        ]
        print(
            tabulate(
                display_rows,
                tablefmt="simple",
                colalign=colalign,
            )
        )
    elif format == "double-line":
        display_rows = [
            (
                entry["date"],
                entry["description"],
                entry["notes"],
                entry["value"],
            )
            for entry in rows
        ]
        print(
            tabulate(
                display_rows,
                headers=["Date", "Description", "Notes", "Value"],
                tablefmt="simple",
            )
        )
    else:
        raise ValueError(f"Unrecognized format: {format}")


def get_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate a General Ledger report from a GnuCash database."
    )
    parser.add_argument(
        "filters", nargs="*", help="Grep-style filters for transactions."
    )
    parser.add_argument(
        "--begin",
        default="-30d",
        help="Start date for transactions"
        " (YYYY-MM-DD or offset, default: today - 30d).",
    )
    parser.add_argument(
        "--end",
        default="0d",
        help="End date for transactions (YYYY-MM-DD or offset, default: today).",
    )
    parser.add_argument(
        "--accounts",
        nargs="*",
        default=[],
        help="List of accounts to include (regex supported).",
    )
    parser.add_argument(
        "--format",
        choices=["single-line", "double-line", "full"],
        default="single-line",
        help="Output format of the ledger.",
    )
    parser.add_argument(
        "-i", action="store_true", help="Ignore case in filters."
    )
    parser.add_argument(
        "-F",
        action="store_true",
        help="Interpret filters as fixed strings, not regular expressions.",
    )
    default_filename = os.getenv("_gc__default_filename", None)
    required = default_filename is None
    parser.add_argument(
        "--file",
        default=default_filename,
        required=required,
        help="Path to the GnuCash file (SQLite3 backend).",
    )
    parser.add_argument(
        "-v",
        action="store_true",
        help="Invert the sense of matching for filters.",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print debugging info."
    )

    args = parser.parse_args()
    return args


def main():
    """Do what we do."""
    args = get_args()
    regex_flags = 0
    if args.i:
        regex_flags |= re.IGNORECASE
    if args.F:
        filters = [re.escape(f) for f in args.filters]
    else:
        filters = args.filters

    # Parse dates.
    begin_date = parse_date_or_offset(args.begin)
    end_date = parse_date_or_offset(args.end)

    # Open the GnuCash database.
    book = piecash.open_book(args.file, open_if_lock=True, readonly=True)

    # Each of these functions returns a list.  We're not trying to be
    # clever yet, and the assumption is that the book is not so large
    # that it's worth losing code readability for performance.
    accounts = filter_accounts(book, args.accounts, args.verbose)
    splits = filter_splits_by_date(
        begin_date, end_date, accounts, args.verbose
    )
    filtered_splits = filter_transactions(
        splits, filters, regex_flags, args.verbose
    )
    print_splits(filtered_splits, args.format)


if __name__ == "__main__":
    main()

"""
TODO:

 * Sort by date at display time.
 * Check that accounts are the same type.
 * Add option for sum of numbers

Needs tests.

"""
