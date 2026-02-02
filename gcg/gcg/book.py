"""
GnuCash book opening and access layer.

Wraps piecash for book opening and provides helpers for common operations.
Ensures read-only access to protect user data.
"""

import sqlite3
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from piecash import open_book
from piecash.core.book import Book


class BookOpenError(Exception):
    """Raised when the book cannot be opened."""

    pass


@dataclass
class BookInfo:
    """Information about an open book."""

    path: Path
    default_currency: str
    has_notes_column: bool
    has_slots_notes: bool
    account_count: int
    transaction_count: int


def check_notes_support(db_path: Path) -> tuple[bool, bool]:
    """
    Check whether the schema supports transaction notes.

    Returns:
        (has_notes_column, has_slots_notes): tuple indicating:
        - has_notes_column: True if transactions table has notes column
        - has_slots_notes: True if notes are stored in slots table
    """
    uri = f"file:{db_path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        cursor = conn.cursor()

        # Check for notes column in transactions table
        cursor.execute("PRAGMA table_info(transactions)")
        columns = {row[1] for row in cursor.fetchall()}
        has_notes_column = "notes" in columns

        # Check for notes in slots (GnuCash stores tx notes as slots)
        has_slots_notes = False
        cursor.execute(
            "SELECT COUNT(*) FROM slots WHERE name = 'notes' "
            "AND obj_guid IN (SELECT guid FROM transactions) LIMIT 1"
        )
        result = cursor.fetchone()
        if result and result[0] > 0:
            has_slots_notes = True

        conn.close()
        return (has_notes_column, has_slots_notes)

    except sqlite3.Error:
        return (False, False)


def get_transaction_notes(
    db_path: Path, tx_guid: str, has_notes_column: bool
) -> Optional[str]:
    """
    Get notes for a transaction.

    Looks up notes either from the transactions table column
    or from the slots table, depending on schema.
    """
    uri = f"file:{db_path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        cursor = conn.cursor()

        if has_notes_column:
            cursor.execute(
                "SELECT notes FROM transactions WHERE guid = ?", (tx_guid,)
            )
        else:
            cursor.execute(
                "SELECT string_val FROM slots "
                "WHERE obj_guid = ? AND name = 'notes'",
                (tx_guid,),
            )

        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

    except sqlite3.Error:
        return None


@contextmanager
def open_gnucash_book(
    path: Path, check_notes: bool = True
) -> Iterator[tuple[Book, BookInfo]]:
    """
    Open a GnuCash book in read-only mode.

    This is the primary entry point for opening books. It:
    - Opens the SQLite file in read-only mode
    - Determines notes support
    - Returns book info alongside the book object

    Args:
        path: Path to the GnuCash SQLite file
        check_notes: Whether to check for notes support (default True)

    Yields:
        Tuple of (Book, BookInfo)

    Raises:
        BookOpenError: If the book cannot be opened
    """
    path = Path(path).expanduser().resolve()

    if not path.exists():
        raise BookOpenError(f"Book file not found: {path}")

    if not path.is_file():
        raise BookOpenError(f"Not a file: {path}")

    # Check notes support before opening with piecash
    has_notes_column = False
    has_slots_notes = False
    if check_notes:
        has_notes_column, has_slots_notes = check_notes_support(path)

    try:
        # Open with piecash in read-only mode
        # piecash uses SQLAlchemy which opens read-only via readonly=True
        book = open_book(str(path), readonly=True, open_if_lock=True)
    except Exception as e:
        raise BookOpenError(f"Failed to open book: {e}") from e

    try:
        # Get book info
        default_currency = (
            book.default_currency.mnemonic if book.default_currency else "EUR"
        )

        # Count accounts and transactions
        account_count = len(
            [a for a in book.accounts if a.type not in ("ROOT", "TRADING")]
        )
        transaction_count = len(book.transactions)

        info = BookInfo(
            path=path,
            default_currency=default_currency,
            has_notes_column=has_notes_column,
            has_slots_notes=has_slots_notes,
            account_count=account_count,
            transaction_count=transaction_count,
        )

        yield book, info

    finally:
        book.close()


def get_account_full_name(account) -> str:
    """Get the full hierarchical name of an account."""
    return account.fullname


def get_account_by_pattern(
    book: Book,
    pattern: str,
    is_regex: bool = False,
    case_sensitive: bool = False,
    include_subtree: bool = True,
) -> list:
    """
    Find accounts matching a pattern.

    Args:
        book: Open GnuCash book
        pattern: Search pattern (substring or regex)
        is_regex: Treat pattern as regex
        case_sensitive: Use case-sensitive matching
        include_subtree: Include descendant accounts of matches

    Returns:
        List of matching Account objects
    """
    import re

    accounts = [a for a in book.accounts if a.type not in ("ROOT", "TRADING")]

    flags = 0 if case_sensitive else re.IGNORECASE

    if is_regex:
        try:
            compiled = re.compile(pattern, flags)
        except re.error as e:
            print(f"Invalid regex pattern: {e}", file=sys.stderr)
            sys.exit(2)
        matches = [a for a in accounts if compiled.search(a.fullname)]
    else:
        if not case_sensitive:
            pattern_lower = pattern.lower()
            matches = [
                a for a in accounts if pattern_lower in a.fullname.lower()
            ]
        else:
            matches = [a for a in accounts if pattern in a.fullname]

    if not include_subtree:
        return matches

    # Include all descendants of matched accounts
    matched_set = set(matches)
    result_set = set(matches)

    for account in accounts:
        # Check if any ancestor is in matched_set
        parent = account.parent
        while parent is not None:
            if parent in matched_set:
                result_set.add(account)
                break
            parent = parent.parent

    return list(result_set)
