#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""Print a General Ledger report from a GnuCash database.

Options permit filtering by account, date, and transaction text.

"""

import argparse
import datetime
import os
import re

import dateparser
import piecash
from tabulate import tabulate

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


def parse_date_or_offset(input_str, end_of_year=False):
    """Parse a date string or a day offset.

    It understands what dateparser.parse() understands.

    """
    if re.match(r"^\d{4}$", input_str):
        # Input is a year, return January 1st of that year
        year = int(input_str)
        if end_of_year:
            return datetime.date(year, 12, 31)
        return datetime.date(year, 1, 1)
    return dateparser.parse(
        input_str,
        date_formats=(
            "%Y-%m-%d",
            "%d-%m-%Y",
        ),
    ).date()


def filter_accounts(book, accounts, verbose):
    """Return a list of accounts matching a list of regexes.

    The argument accounts is a list of regular expressions.

    TODO: Verify that all accounts are the same type so that the union
    makes sense.

    """
    if verbose:
        print(f"Book has {len(book.accounts)} accounts.")
        print(f"Filtering accounts on regexes: {accounts}")
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
    sorted_splits = sorted(
        splits, key=lambda split: split.transaction.post_date
    )
    return sorted_splits


def filter_transactions(splits, filters, flags, verbose):
    """Apply grep-style filters to transaction splits."""
    if not filters:
        if verbose:
            print("No filters specified, using all transactions.")
        return splits
    if verbose:
        print(
            f"Applying {len(filters)} filters to {len(splits)}"
            f" transactions: {filters}."
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


def amount_with_currency(amount, currency, sign):
    """Return a string with a signed amount and currency symbol."""
    amount *= sign
    if currency == "USD":
        return f"${amount:.2f}"
    if currency == "EUR":
        return f"€{amount:.2f}"
    if currency == "GBP":
        return f"£{amount:.2f}"
    return f"{amount:.2f} {currency}"


def prepare_splits_for_printing(splits):
    """Do some common preprocessing on splits for printing."""
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
                "is_debit": split.is_debit,
                "is_credit": split.is_credit,
            }
        )
    return rows


def print_splits_full(splits):
    """Print a list of splits with full split detail.

    This isn't quite right, as I'd like to show the splits grouped by
    their transaction.  But it's a start, at least it shows the
    account name.


    """
    rows = prepare_splits_for_printing(splits)
    display_rows = [
        (
            entry["date"],
            entry["description"],
            entry["notes"],
            entry["account"],
            (
                amount_with_currency(entry["value"], entry["currency"], 1)
                if entry["is_debit"]
                else ""
            ),
            (
                amount_with_currency(entry["value"], entry["currency"], -1)
                if entry["is_credit"]
                else ""
            ),
        )
        for entry in rows
    ]
    if not display_rows:
        print("No matching transactions.")
        return
    print(
        tabulate(
            display_rows,
            headers=[
                "Date",
                "Description",
                "Notes",
                "Account",
                "Debit",
                "Credit",
            ],
            tablefmt="simple",
        )
    )

    print("Full split detail is not yet implemented.")
    return


def print_splits_single_line(splits):
    """Print a list of splits with a single line per split."""
    rows = prepare_splits_for_printing(splits)
    colalign = ("left", "left", "right", "right")
    display_rows = [
        (
            entry["date"],
            entry["description"],
            (
                amount_with_currency(entry["value"], entry["currency"], 1)
                if entry["is_debit"]
                else ""
            ),
            (
                amount_with_currency(entry["value"], entry["currency"], -1)
                if entry["is_credit"]
                else ""
            ),
        )
        for entry in rows
    ]
    if not display_rows:
        print("No matching transactions.")
        return
    print(
        tabulate(
            display_rows,
            headers=["Date", "Description", "Debit", "Credit"],
            tablefmt="simple",
            colalign=colalign,
        )
    )


def print_splits_double_line(splits):
    """Print a list of splits with a double line per split."""
    rows = prepare_splits_for_printing(splits)
    display_rows = [
        (
            entry["date"],
            entry["description"],
            entry["notes"],
            (
                amount_with_currency(entry["value"], entry["currency"], 1)
                if entry["is_debit"]
                else ""
            ),
            (
                amount_with_currency(entry["value"], entry["currency"], -1)
                if entry["is_credit"]
                else ""
            ),
        )
        for entry in rows
    ]
    if not display_rows:
        print("No matching transactions.")
        return
    print(
        tabulate(
            display_rows,
            headers=["Date", "Description", "Notes", "Debit", "Credit"],
            tablefmt="simple",
        )
    )


def print_splits(splits, output_format):
    """Print a list of splits in a specified format."""
    if output_format == "full":
        print_splits_full(splits)
        return
    if output_format == "single":
        print_splits_single_line(splits)
        return
    if output_format == "double":
        print_splits_double_line(splits)
        return
    raise ValueError(f"Unrecognized format: {output_format}")


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
        default="-3y",
        help="Start date for transactions"
        " (YYYY-MM-DD, YYYY (first day of year), or offset,"
        " default: 3 years ago today).",
    )
    parser.add_argument(
        "--end",
        default="0d",
        help="End date for transactions (YYYY-MM-DD, YYYY (last day of year)"
        " or offset, default: today).",
    )
    parser.add_argument(
        "--year", default=None, help="Equavalent to --begin YYYY --end YYYY."
    )
    parser.add_argument(
        "--accounts",
        nargs="*",
        default=[],
        help="List of accounts to include (regex supported).",
    )
    parser.add_argument(
        "--format",
        choices=["single", "double", "full"],
        default="single",
        help="Output format of the ledger (single, double, full),"
        " default single.",
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
        "--invert-match",
        action="store_true",
        help="Invert the sense of matching for filters.",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Print debugging info."
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
    if args.year:
        args.begin = args.year
        args.end = args.year
    begin_date = parse_date_or_offset(args.begin, end_of_year=False)
    end_date = parse_date_or_offset(args.end, end_of_year=True)
    if args.verbose:
        print(f"Considering transactions from {begin_date} to {end_date}.")

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
