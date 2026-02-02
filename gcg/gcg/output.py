"""
Output formatting for gcg.

Supports table, CSV, and JSON output formats with configurable columns.
"""

import csv
import json
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from tabulate import tabulate

# Default columns for split output
DEFAULT_SPLIT_COLUMNS = [
    "date",
    "description",
    "account",
    "memo",
    "amount",
    "currency",
    "tx_guid",
    "split_guid",
]

# Default columns for account output
DEFAULT_ACCOUNT_COLUMNS = [
    "name",
    "type",
    "currency",
]


@dataclass
class SplitRow:
    """Represents a split row for output."""

    date: date
    description: str
    account: str
    memo: Optional[str]
    notes: Optional[str]
    amount: Decimal
    currency: str
    fx_rate: Optional[Decimal]
    tx_guid: str
    split_guid: str
    account_guid: Optional[str] = None
    amount_orig: Optional[Decimal] = None
    currency_orig: Optional[str] = None

    def to_dict(self, include_notes: bool = True) -> dict[str, Any]:
        """Convert to dictionary for JSON/CSV output."""
        result = {
            "date": self.date.isoformat(),
            "description": self.description,
            "account": self.account,
            "memo": self.memo or "",
            "amount": str(self.amount),
            "currency": self.currency,
            "tx_guid": self.tx_guid,
            "split_guid": self.split_guid,
        }

        if include_notes and self.notes:
            result["notes"] = self.notes

        if self.fx_rate is not None:
            result["fx_rate"] = str(self.fx_rate)
        else:
            result["fx_rate"] = None

        if self.account_guid:
            result["account_guid"] = self.account_guid

        if self.amount_orig is not None:
            result["amount_orig"] = str(self.amount_orig)
            result["currency_orig"] = self.currency_orig

        return result


@dataclass
class TransactionRow:
    """Represents a transaction with its splits for full-tx output."""

    tx_guid: str
    date: date
    description: str
    notes: Optional[str]
    splits: list[SplitRow]

    def to_dict(self, include_notes: bool = True) -> dict[str, Any]:
        """Convert to dictionary for JSON output."""
        result = {
            "tx_guid": self.tx_guid,
            "date": self.date.isoformat(),
            "description": self.description,
            "splits": [s.to_dict(include_notes) for s in self.splits],
        }
        if include_notes and self.notes:
            result["notes"] = self.notes
        return result


@dataclass
class AccountRow:
    """Represents an account row for output."""

    name: str
    type: str
    currency: str
    guid: Optional[str] = None
    depth: int = 0  # For tree display

    def to_dict(self, show_guid: bool = False) -> dict[str, Any]:
        """Convert to dictionary for JSON/CSV output."""
        result = {
            "name": self.name,
            "type": self.type,
            "currency": self.currency,
        }
        if show_guid and self.guid:
            result["guid"] = self.guid
        return result


class OutputFormatter:
    """Formats output in various formats."""

    def __init__(
        self,
        format_type: str = "table",
        show_header: bool = True,
        fields: Optional[list[str]] = None,
        include_notes: bool = True,
        show_guids: bool = False,
    ):
        """
        Initialize formatter.

        Args:
            format_type: "table", "csv", or "json"
            show_header: Include header row (table/csv)
            fields: Custom field list (None for defaults)
            include_notes: Include notes field if available
            show_guids: Include GUID fields in account output
        """
        self.format_type = format_type
        self.show_header = show_header
        self.fields = fields
        self.include_notes = include_notes
        self.show_guids = show_guids

    def format_splits(
        self,
        rows: list[SplitRow],
        file=None,
    ) -> None:
        """
        Format and output split rows.

        Args:
            rows: List of SplitRow objects
            file: Output file (default: stdout)
        """
        if file is None:
            file = sys.stdout

        if not rows:
            return

        if self.format_type == "json":
            self._format_splits_json(rows, file)
        elif self.format_type == "csv":
            self._format_splits_csv(rows, file)
        else:
            self._format_splits_table(rows, file)

    def format_transactions(
        self,
        rows: list[TransactionRow],
        file=None,
    ) -> None:
        """
        Format and output transaction rows (for --full-tx).

        Args:
            rows: List of TransactionRow objects
            file: Output file (default: stdout)
        """
        if file is None:
            file = sys.stdout

        if not rows:
            return

        if self.format_type == "json":
            self._format_transactions_json(rows, file)
        elif self.format_type == "csv":
            # CSV flattens to splits with tx info
            all_splits = []
            for tx in rows:
                for split in tx.splits:
                    all_splits.append(split)
            self._format_splits_csv(all_splits, file)
        else:
            self._format_transactions_table(rows, file)

    def format_accounts(
        self,
        rows: list[AccountRow],
        tree_mode: bool = False,
        file=None,
    ) -> None:
        """
        Format and output account rows.

        Args:
            rows: List of AccountRow objects
            tree_mode: Display as tree with indentation
            file: Output file (default: stdout)
        """
        if file is None:
            file = sys.stdout

        if not rows:
            return

        if self.format_type == "json":
            self._format_accounts_json(rows, file)
        elif self.format_type == "csv":
            self._format_accounts_csv(rows, file)
        else:
            self._format_accounts_table(rows, tree_mode, file)

    def _format_splits_table(self, rows: list[SplitRow], file) -> None:
        """Format splits as a table."""
        headers = ["Date", "Description", "Account", "Memo", "Amount", "Ccy"]

        # Check if we need notes column
        has_notes = self.include_notes and any(r.notes for r in rows)
        if has_notes:
            headers.insert(4, "Notes")

        # Check if we have original amounts
        has_orig = any(r.amount_orig is not None for r in rows)
        if has_orig:
            headers.extend(["Orig Amt", "Orig Ccy"])

        table_data = []
        for row in rows:
            line = [
                str(row.date),
                _truncate(row.description, 40),
                _truncate(row.account, 35),
                _truncate(row.memo or "", 25),
                _format_amount(row.amount),
                row.currency,
            ]
            if has_notes:
                line.insert(4, _truncate(row.notes or "", 25))
            if has_orig:
                line.extend(
                    [
                        (
                            _format_amount(row.amount_orig)
                            if row.amount_orig
                            else ""
                        ),
                        row.currency_orig or "",
                    ]
                )
            table_data.append(line)

        if self.show_header:
            print(
                tabulate(table_data, headers=headers, tablefmt="simple"),
                file=file,
            )
        else:
            print(tabulate(table_data, tablefmt="plain"), file=file)

    def _format_splits_csv(self, rows: list[SplitRow], file) -> None:
        """Format splits as CSV."""
        if not rows:
            return

        # Determine columns
        fieldnames = [
            "date",
            "description",
            "account",
            "memo",
            "amount",
            "currency",
            "fx_rate",
            "tx_guid",
            "split_guid",
        ]

        has_notes = self.include_notes and any(r.notes for r in rows)
        if has_notes:
            fieldnames.insert(4, "notes")

        has_orig = any(r.amount_orig is not None for r in rows)
        if has_orig:
            fieldnames.extend(["amount_orig", "currency_orig"])

        writer = csv.DictWriter(
            file, fieldnames=fieldnames, extrasaction="ignore"
        )
        if self.show_header:
            writer.writeheader()

        for row in rows:
            writer.writerow(row.to_dict(self.include_notes))

    def _format_splits_json(self, rows: list[SplitRow], file) -> None:
        """Format splits as JSON array."""
        data = [row.to_dict(self.include_notes) for row in rows]
        json.dump(data, file, indent=2, ensure_ascii=False)
        print(file=file)

    def _format_transactions_table(
        self, rows: list[TransactionRow], file
    ) -> None:
        """Format transactions with their splits as table blocks."""
        for i, tx in enumerate(rows):
            if i > 0:
                print(file=file)  # Blank line between transactions

            # Transaction header
            print(f"[{tx.date}] {tx.description}", file=file)
            if tx.notes:
                print(f"  Notes: {tx.notes}", file=file)
            print(f"  GUID: {tx.tx_guid}", file=file)

            # Splits
            for split in tx.splits:
                amount_str = _format_amount(split.amount)
                print(
                    f"    {split.account:<40} {amount_str:>12} "
                    f"{split.currency}",
                    file=file,
                )
                if split.memo:
                    print(f"      Memo: {split.memo}", file=file)

    def _format_transactions_json(
        self, rows: list[TransactionRow], file
    ) -> None:
        """Format transactions as JSON array."""
        data = [row.to_dict(self.include_notes) for row in rows]
        json.dump(data, file, indent=2, ensure_ascii=False)
        print(file=file)

    def _format_accounts_table(
        self, rows: list[AccountRow], tree_mode: bool, file
    ) -> None:
        """Format accounts as table."""
        headers = ["Account", "Type", "Currency"]
        if self.show_guids:
            headers.append("GUID")

        table_data = []
        for row in rows:
            if tree_mode:
                # Indent based on depth
                indent = "  " * row.depth
                name = indent + row.name.split(":")[-1]
            else:
                name = row.name

            line = [name, row.type, row.currency]
            if self.show_guids:
                line.append(row.guid or "")
            table_data.append(line)

        if self.show_header:
            print(
                tabulate(table_data, headers=headers, tablefmt="simple"),
                file=file,
            )
        else:
            print(tabulate(table_data, tablefmt="plain"), file=file)

    def _format_accounts_csv(self, rows: list[AccountRow], file) -> None:
        """Format accounts as CSV."""
        fieldnames = ["name", "type", "currency"]
        if self.show_guids:
            fieldnames.append("guid")

        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if self.show_header:
            writer.writeheader()

        for row in rows:
            writer.writerow(row.to_dict(self.show_guids))

    def _format_accounts_json(self, rows: list[AccountRow], file) -> None:
        """Format accounts as JSON array."""
        data = [row.to_dict(self.show_guids) for row in rows]
        json.dump(data, file, indent=2, ensure_ascii=False)
        print(file=file)


def _truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis if too long."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _format_amount(amount: Optional[Decimal]) -> str:
    """Format a decimal amount for display."""
    if amount is None:
        return ""
    # Format with 2 decimal places, right-aligned
    return f"{amount:,.2f}"
