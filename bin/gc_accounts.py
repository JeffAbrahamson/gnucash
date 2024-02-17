#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""Filter and display GnuCash account names."""

import os
import argparse
import re
import piecash


gpl = """
Copyright 2024  Jeff Abrahamson

This file is part of gc_accounts.py.

gc_accounts.py is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

gc_accounts.py is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with gc_accounts.py.  If not, see <http://www.gnu.org/licenses/>.
"""


def filter_accounts(accounts, pattern, flags):
    """Filter accounts based on pattern and flags."""
    regex_flags = 0
    if flags.ignore_case:
        regex_flags |= re.IGNORECASE
    if flags.fixed_strings:
        pattern = re.escape(pattern)

    matched_accounts = []
    for account in accounts:
        if (
            re.search(pattern, account.name, regex_flags) is not None
        ) != flags.invert_match:
            matched_accounts.append(account)
    return matched_accounts


def print_accounts(accounts, show_tree, leaf_only):
    """Print accounts, optionally in tree format or leaf nodes only."""
    if show_tree:
        # This is a simplified placeholder for tree-view logic.
        for account in accounts:
            print(dir(account))
            print("  " * account.depth + account.name)
    elif leaf_only:
        for account in accounts:
            if not account.children:
                print(account.name)
    else:
        for account in accounts:
            print(account.name)


def compile_pattern(patterns, ignore_case, fixed_strings):
    """Compile the pattern(s) into a regular expression object."""
    flags = re.IGNORECASE if ignore_case else 0
    combined_pattern = (
        "|".join(map(re.escape, patterns))
        if fixed_strings
        else "|".join(patterns)
    )
    return re.compile(combined_pattern, flags)


def should_account_be_included(account, regex):
    """Determine if an account matches the filtering criteria."""
    return bool(regex.search(account.name))


def print_account_tree(account, regex, indent=0, leaf_only=False):
    """Recursively walk and print the account tree, applying filtering."""
    if (
        should_account_be_included(account, regex) or indent == 0
    ):  # Always include root
        if not leaf_only or (leaf_only and not account.children):
            print("  " * indent + account.name)
        for child in account.children:
            print_account_tree(child, regex, indent + 1, leaf_only)


def main():
    parser = argparse.ArgumentParser(
        description="Filter and display GnuCash account names."
    )
    parser.add_argument(
        "pattern",
        nargs="*",
        help="Grep-style pattern for filtering account names.",
    )
    parser.add_argument(
        "-F",
        "--fixed-strings",
        action="store_true",
        help="Interpret pattern as fixed strings.",
    )
    parser.add_argument(
        "-v",
        "--invert-match",
        action="store_true",
        help="Invert the sense of matching.",
    )
    parser.add_argument(
        "-i",
        "--ignore-case",
        action="store_true",
        help="Perform case insensitive matching.",
    )
    parser.add_argument(
        "--leaf-only",
        action="store_true",
        help="Show only leaf accounts (those without children).",
    )
    parser.add_argument(
        "--show-tree",
        action="store_true",
        help="Display accounts in a tree structure.",
    )
    parser.add_argument(
        "--always-include-root",
        action="store_false",
        help="Always display root accounts in tree view,"
        " even if they don't not match the pattern.",
    )
    default_filename = os.getenv("_gc__default_filename", None)
    required = default_filename is None
    parser.add_argument(
        "--file",
        default=default_filename,
        required=required,
        help="Path to the GnuCash file (SQLite3 backend).",
    )

    args = parser.parse_args()

    with piecash.open_book(
        args.file, readonly=True, open_if_lock=True
    ) as book:
        if args.show_tree:
            regex = compile_pattern(
                args.pattern, args.ignore_case, args.fixed_strings
            )
            root_accounts = [
                account
                for account in book.accounts
                if account.parent.parent is None
            ]
            print(root_accounts)
            for root_account in root_accounts:
                print_account_tree(
                    root_account, regex, leaf_only=args.leaf_only
                )
        else:
            accounts = book.accounts
            if args.pattern:
                combined_pattern = "|".join(args.pattern)
                accounts = filter_accounts(accounts, combined_pattern, args)
            accounts = sorted(accounts, key=lambda x: x.name)

            print_accounts(accounts, args.show_tree, args.leaf_only)


if __name__ == "__main__":
    main()
