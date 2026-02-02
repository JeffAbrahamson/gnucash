"""
Interactive REPL mode for gcg.

Provides a readline-enabled interactive shell for querying
GnuCash books without repeatedly loading them.
"""

import re
import readline
import shlex
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

from gcg.book import (
    BookOpenError,
    InvalidPatternError,
    get_account_by_pattern,
    get_transaction_notes,
    get_transaction_notes_batch,
    open_gnucash_book,
)
from gcg.config import Config, get_xdg_state_home
from gcg.output import (
    AccountRow,
    OutputFormatter,
    SplitRow,
    TransactionRow,
)


class ReplSession:
    """
    Interactive REPL session for gcg.

    Maintains state between commands and provides readline support
    with command history. Keeps the book open between commands for
    faster repeated queries.
    """

    def __init__(self, config: Config):
        """
        Initialize REPL session.

        Args:
            config: gcg configuration
        """
        self.config = config
        self.book = None
        self.book_info = None
        self.book_path = None
        self.running = True

        # Session settings (can be changed with 'set' command)
        self.output_format = config.output_format
        self.currency_mode = config.currency_mode
        self.base_currency = config.base_currency

        # History file
        self.history_path = config.history_path or (
            get_xdg_state_home() / "gcg" / "history"
        )

    def setup_readline(self) -> None:
        """Configure readline with history and completion."""
        # Create history directory if needed
        self.history_path.parent.mkdir(parents=True, exist_ok=True)

        # Load history
        if self.history_path.exists():
            try:
                readline.read_history_file(str(self.history_path))
            except (OSError, IOError):
                pass

        # Set history length
        readline.set_history_length(1000)

        # Basic tab completion
        commands = [
            "open",
            "accounts",
            "grep",
            "ledger",
            "tx",
            "split",
            "set",
            "help",
            "quit",
            "exit",
        ]
        readline.set_completer(
            lambda text, state: (
                [c for c in commands if c.startswith(text)] + [None]
            )[state]
        )
        readline.parse_and_bind("tab: complete")

    def save_history(self) -> None:
        """Save command history to file."""
        try:
            readline.write_history_file(str(self.history_path))
        except (OSError, IOError):
            pass

    def open_book(self, path: Optional[str] = None) -> bool:
        """
        Open a GnuCash book.

        Args:
            path: Path to book file, or None to use config default

        Returns:
            True if book opened successfully
        """
        # Close existing book first
        self.close_book()

        book_path = (
            Path(path).expanduser().resolve()
            if path
            else self.config.resolve_book_path()
        )

        try:
            # Use the context manager properly via __enter__/__exit__
            # We store the generator to call __exit__ later
            self._book_ctx = open_gnucash_book(book_path)
            self.book, self.book_info = self._book_ctx.__enter__()
            self.book_path = book_path
            print(f"Opened: {book_path}")
            print(f"  Accounts: {self.book_info.account_count}")
            print(f"  Transactions: {self.book_info.transaction_count}")
            return True

        except BookOpenError as e:
            print(f"Error: {e}", file=sys.stderr)
            self._book_ctx = None
            return False

    def close_book(self) -> None:
        """Close the current book if open."""
        if self.book is not None and hasattr(self, "_book_ctx"):
            try:
                self._book_ctx.__exit__(None, None, None)
            except Exception:
                pass  # Ignore cleanup errors
        self.book = None
        self.book_info = None
        self.book_path = None
        self._book_ctx = None

    def run_command(self, line: str) -> None:
        """
        Parse and execute a REPL command.

        Args:
            line: Command line input
        """
        line = line.strip()
        if not line or line.startswith("#"):
            return

        try:
            parts = shlex.split(line)
        except ValueError as e:
            print(f"Parse error: {e}", file=sys.stderr)
            return

        if not parts:
            return

        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ("quit", "exit"):
            self.running = False
            return

        if cmd == "help":
            self.cmd_help(args)
            return

        if cmd == "open":
            if args:
                self.open_book(args[0])
            else:
                self.open_book()
            return

        if cmd == "set":
            self.cmd_set(args)
            return

        # Commands that require an open book
        if self.book is None:
            print("No book open. Use 'open [path]' first.", file=sys.stderr)
            return

        if cmd == "accounts":
            self.cmd_accounts(args)
        elif cmd == "grep":
            self.cmd_grep(args)
        elif cmd == "ledger":
            self.cmd_ledger(args)
        elif cmd == "tx":
            self.cmd_tx(args)
        elif cmd == "split":
            self.cmd_split(args)
        else:
            print(
                f"Unknown command: {cmd}. Type 'help' for commands.",
                file=sys.stderr,
            )

    def cmd_help(self, args: list[str]) -> None:
        """Display help information."""
        print("""
gcg REPL Commands:

  open [PATH]       Open a GnuCash book (default: configured path)
  accounts [PATTERN] [OPTIONS]
                    Search accounts by pattern
  grep TEXT [OPTIONS]
                    Search splits/transactions for text
  ledger ACCOUNT [OPTIONS]
                    Display ledger for accounts
  tx GUID           Show transaction by GUID
  split GUID        Show split by GUID

  set format table|csv|json
                    Set output format
  set currency auto|base|split|account
                    Set currency display mode
  set base-currency CUR
                    Set base currency for conversions

  help              Show this help
  quit / exit       Exit the REPL

Options are the same as CLI. Example:
  grep amazon --after 2025-01-01 --amount 10..100
  ledger "Assets:Bank" --currency account
""")

    def cmd_set(self, args: list[str]) -> None:
        """Handle the 'set' command."""
        if len(args) < 2:
            print("Current settings:")
            print(f"  format: {self.output_format}")
            print(f"  currency: {self.currency_mode}")
            print(f"  base-currency: {self.base_currency}")
            return

        setting = args[0].lower()
        value = args[1]

        if setting == "format":
            if value in ("table", "csv", "json"):
                self.output_format = value
                print(f"Output format set to: {value}")
            else:
                print("Invalid format. Use: table, csv, json")

        elif setting == "currency":
            if value in ("auto", "base", "split", "account"):
                self.currency_mode = value
                print(f"Currency mode set to: {value}")
            else:
                print("Invalid mode. Use: auto, base, split, account")

        elif setting == "base-currency":
            self.base_currency = value.upper()
            print(f"Base currency set to: {self.base_currency}")

        else:
            print(f"Unknown setting: {setting}")

    def cmd_accounts(self, args: list[str]) -> None:
        """Handle the 'accounts' command in REPL using the open book."""
        # Parse arguments
        import argparse

        parser = argparse.ArgumentParser(prog="accounts")
        parser.add_argument("pattern", nargs="?", default="")
        parser.add_argument("--regex", action="store_true")
        parser.add_argument("--case-sensitive", action="store_true")
        parser.add_argument("--tree", action="store_true")
        parser.add_argument("--tree-prune", action="store_true")
        parser.add_argument("--max-depth", type=int)
        parser.add_argument("--show-guids", action="store_true")
        parser.add_argument("--no-header", action="store_true")
        parser.add_argument("--limit", type=int)
        parser.add_argument("--offset", type=int)

        try:
            parsed = parser.parse_args(args)
        except SystemExit:
            return

        try:
            accounts = get_account_by_pattern(
                self.book,
                parsed.pattern,
                is_regex=parsed.regex,
                case_sensitive=parsed.case_sensitive,
            )
        except InvalidPatternError as e:
            print(f"Error: {e}", file=sys.stderr)
            return

        if not accounts:
            print("No matching accounts.")
            return

        accounts.sort(key=lambda a: a.fullname)

        rows = []
        for acc in accounts:
            depth = acc.fullname.count(":") if parsed.tree else 0
            rows.append(
                AccountRow(
                    name=acc.fullname,
                    type=acc.type,
                    currency=acc.commodity.mnemonic if acc.commodity else "",
                    guid=acc.guid if parsed.show_guids else None,
                    depth=depth,
                )
            )

        if parsed.offset:
            rows = rows[parsed.offset :]
        if parsed.limit:
            rows = rows[: parsed.limit]

        formatter = OutputFormatter(
            format_type=self.output_format,
            show_header=not parsed.no_header,
            show_guids=parsed.show_guids,
        )
        formatter.format_accounts(rows, tree_mode=parsed.tree)

    def cmd_grep(self, args: list[str]) -> None:
        """Handle the 'grep' command in REPL using the open book."""
        if not args:
            print("Usage: grep TEXT [OPTIONS]", file=sys.stderr)
            return

        import argparse

        parser = argparse.ArgumentParser(prog="grep")
        parser.add_argument("text")
        parser.add_argument("--regex", action="store_true")
        parser.add_argument("--case-sensitive", action="store_true")
        parser.add_argument("--in", dest="search_fields", default="desc,memo")
        parser.add_argument("--account", metavar="PATTERN")
        parser.add_argument("--account-regex", action="store_true")
        parser.add_argument("--no-subtree", action="store_true")
        parser.add_argument("--after", type=str)
        parser.add_argument("--before", type=str)
        parser.add_argument("--amount", type=str)
        parser.add_argument("--signed", action="store_true")
        parser.add_argument("--full-tx", action="store_true")
        parser.add_argument("--no-header", action="store_true")
        parser.add_argument("--limit", type=int)
        parser.add_argument("--offset", type=int)
        parser.add_argument("--sort", default="date")
        parser.add_argument("--reverse", action="store_true")

        try:
            parsed = parser.parse_args(args)
        except SystemExit:
            return

        # Compile pattern
        flags = 0 if parsed.case_sensitive else re.IGNORECASE
        if parsed.regex:
            try:
                pattern = re.compile(parsed.text, flags)
            except re.error as e:
                print(f"Invalid regex: {e}", file=sys.stderr)
                return
        else:
            pattern = re.compile(re.escape(parsed.text), flags)

        # Parse dates
        after_date = None
        before_date = None
        if parsed.after:
            try:
                after_date = date.fromisoformat(parsed.after)
            except ValueError:
                print(f"Invalid date: {parsed.after}", file=sys.stderr)
                return
        if parsed.before:
            try:
                before_date = date.fromisoformat(parsed.before)
            except ValueError:
                print(f"Invalid date: {parsed.before}", file=sys.stderr)
                return

        # Parse amount range
        min_amt, max_amt = None, None
        if parsed.amount:
            if ".." in parsed.amount:
                parts = parsed.amount.split("..", 1)
                if parts[0]:
                    min_amt = Decimal(parts[0])
                if parts[1]:
                    max_amt = Decimal(parts[1])

        search_fields = set(parsed.search_fields.split(","))

        # Filter accounts
        if parsed.account:
            try:
                accounts = get_account_by_pattern(
                    self.book,
                    parsed.account,
                    is_regex=parsed.account_regex,
                    case_sensitive=False,
                    include_subtree=not parsed.no_subtree,
                )
            except InvalidPatternError as e:
                print(f"Error: {e}", file=sys.stderr)
                return
            account_set = set(accounts)
        else:
            accounts = [
                a
                for a in self.book.accounts
                if a.type not in ("ROOT", "TRADING")
            ]
            account_set = None

        # Collect matching splits
        matching_splits = []
        seen_tx_guids = set()
        tx_guids_for_notes = set()

        for acc in accounts:
            for split in acc.splits:
                tx = split.transaction

                if account_set and split.account not in account_set:
                    continue

                tx_date = tx.post_date
                if after_date and tx_date < after_date:
                    continue
                if before_date and tx_date >= before_date:
                    continue

                split_value = Decimal(str(split.value))
                if not parsed.signed:
                    split_value = abs(split_value)
                if min_amt is not None and split_value < min_amt:
                    continue
                if max_amt is not None and split_value > max_amt:
                    continue

                searchable = ""
                if "desc" in search_fields:
                    searchable += tx.description + " "
                if "memo" in search_fields:
                    searchable += (split.memo or "") + " "

                if not pattern.search(searchable):
                    continue

                if parsed.full_tx:
                    if tx.guid in seen_tx_guids:
                        continue
                    seen_tx_guids.add(tx.guid)

                matching_splits.append((split, tx, acc))
                tx_guids_for_notes.add(tx.guid)

        if not matching_splits:
            print("No matches found.")
            return

        # Batch fetch notes
        notes_map = get_transaction_notes_batch(
            self.book_path,
            list(tx_guids_for_notes),
            self.book_info.has_notes_column,
        )

        # Convert to rows
        rows = self._splits_to_rows(matching_splits, notes_map, parsed.signed)

        # Sort
        rows = self._sort_rows(rows, parsed.sort, parsed.reverse)

        if parsed.offset:
            rows = rows[parsed.offset :]
        if parsed.limit:
            rows = rows[: parsed.limit]

        formatter = OutputFormatter(
            format_type=self.output_format,
            show_header=not parsed.no_header,
        )

        if parsed.full_tx:
            tx_rows = self._splits_to_transactions(
                matching_splits, notes_map, parsed.signed
            )
            formatter.format_transactions(tx_rows)
        else:
            formatter.format_splits(rows)

    def cmd_ledger(self, args: list[str]) -> None:
        """Handle the 'ledger' command in REPL using the open book."""
        if not args:
            print("Usage: ledger ACCOUNT_PATTERN [OPTIONS]", file=sys.stderr)
            return

        import argparse

        parser = argparse.ArgumentParser(prog="ledger")
        parser.add_argument("account_pattern")
        parser.add_argument("--account-regex", action="store_true")
        parser.add_argument("--no-subtree", action="store_true")
        parser.add_argument("--after", type=str)
        parser.add_argument("--before", type=str)
        parser.add_argument("--amount", type=str)
        parser.add_argument("--signed", action="store_true")
        parser.add_argument("--no-header", action="store_true")
        parser.add_argument("--limit", type=int)
        parser.add_argument("--offset", type=int)
        parser.add_argument("--sort", default="date")
        parser.add_argument("--reverse", action="store_true")

        try:
            parsed = parser.parse_args(args)
        except SystemExit:
            return

        # Parse dates
        after_date = None
        before_date = None
        if parsed.after:
            try:
                after_date = date.fromisoformat(parsed.after)
            except ValueError:
                print(f"Invalid date: {parsed.after}", file=sys.stderr)
                return
        if parsed.before:
            try:
                before_date = date.fromisoformat(parsed.before)
            except ValueError:
                print(f"Invalid date: {parsed.before}", file=sys.stderr)
                return

        # Parse amount range
        min_amt, max_amt = None, None
        if parsed.amount:
            if ".." in parsed.amount:
                parts = parsed.amount.split("..", 1)
                if parts[0]:
                    min_amt = Decimal(parts[0])
                if parts[1]:
                    max_amt = Decimal(parts[1])

        try:
            accounts = get_account_by_pattern(
                self.book,
                parsed.account_pattern,
                is_regex=parsed.account_regex,
                case_sensitive=False,
                include_subtree=not parsed.no_subtree,
            )
        except InvalidPatternError as e:
            print(f"Error: {e}", file=sys.stderr)
            return

        if not accounts:
            print(f"No accounts matching: {parsed.account_pattern}")
            return

        splits_data = []
        tx_guids_for_notes = set()

        for acc in accounts:
            for split in acc.splits:
                tx = split.transaction

                tx_date = tx.post_date
                if after_date and tx_date < after_date:
                    continue
                if before_date and tx_date >= before_date:
                    continue

                split_value = Decimal(str(split.value))
                if not parsed.signed:
                    split_value = abs(split_value)
                if min_amt is not None and split_value < min_amt:
                    continue
                if max_amt is not None and split_value > max_amt:
                    continue

                splits_data.append((split, tx, acc))
                tx_guids_for_notes.add(tx.guid)

        if not splits_data:
            print("No matching splits.")
            return

        notes_map = get_transaction_notes_batch(
            self.book_path,
            list(tx_guids_for_notes),
            self.book_info.has_notes_column,
        )

        rows = self._splits_to_rows(splits_data, notes_map, parsed.signed)
        rows = self._sort_rows(rows, parsed.sort, parsed.reverse)

        if parsed.offset:
            rows = rows[parsed.offset :]
        if parsed.limit:
            rows = rows[: parsed.limit]

        formatter = OutputFormatter(
            format_type=self.output_format,
            show_header=not parsed.no_header,
        )
        formatter.format_splits(rows)

    def cmd_tx(self, args: list[str]) -> None:
        """Handle the 'tx' command in REPL using the open book."""
        if not args:
            print("Usage: tx GUID", file=sys.stderr)
            return

        guid = args[0]
        tx = None
        for t in self.book.transactions:
            if t.guid == guid:
                tx = t
                break

        if tx is None:
            print(f"Transaction not found: {guid}", file=sys.stderr)
            return

        notes = get_transaction_notes(
            self.book_path, tx.guid, self.book_info.has_notes_column
        )

        split_rows = []
        for split in tx.splits:
            acc = split.account
            split_rows.append(
                SplitRow(
                    date=tx.post_date,
                    description=tx.description,
                    account=acc.fullname,
                    memo=split.memo,
                    notes=notes,
                    amount=Decimal(str(split.value)),
                    currency=acc.commodity.mnemonic if acc.commodity else "",
                    fx_rate=None,
                    tx_guid=tx.guid,
                    split_guid=split.guid,
                )
            )

        tx_row = TransactionRow(
            tx_guid=tx.guid,
            date=tx.post_date,
            description=tx.description,
            notes=notes,
            splits=split_rows,
        )

        formatter = OutputFormatter(format_type=self.output_format)
        formatter.format_transactions([tx_row])

    def cmd_split(self, args: list[str]) -> None:
        """Handle the 'split' command in REPL using the open book."""
        if not args:
            print("Usage: split GUID", file=sys.stderr)
            return

        guid = args[0]
        found_split = None
        found_tx = None
        found_acc = None

        for acc in self.book.accounts:
            for split in acc.splits:
                if split.guid == guid:
                    found_split = split
                    found_tx = split.transaction
                    found_acc = acc
                    break
            if found_split:
                break

        if found_split is None:
            print(f"Split not found: {guid}", file=sys.stderr)
            return

        notes = get_transaction_notes(
            self.book_path, found_tx.guid, self.book_info.has_notes_column
        )

        row = SplitRow(
            date=found_tx.post_date,
            description=found_tx.description,
            account=found_acc.fullname,
            memo=found_split.memo,
            notes=notes,
            amount=Decimal(str(found_split.value)),
            currency=(
                found_acc.commodity.mnemonic if found_acc.commodity else ""
            ),
            fx_rate=None,
            tx_guid=found_tx.guid,
            split_guid=found_split.guid,
        )

        formatter = OutputFormatter(format_type=self.output_format)
        formatter.format_splits([row])

    def _splits_to_rows(
        self,
        splits_data: list,
        notes_map: dict[str, str],
        signed: bool,
    ) -> list[SplitRow]:
        """Convert split/tx/acc tuples to SplitRow objects."""
        rows = []
        for split, tx, acc in splits_data:
            split_value = Decimal(str(split.value))
            if not signed:
                split_value = abs(split_value)

            split_currency = acc.commodity.mnemonic if acc.commodity else "???"
            notes = notes_map.get(tx.guid)

            row = SplitRow(
                date=tx.post_date,
                description=tx.description,
                account=acc.fullname,
                memo=split.memo,
                notes=notes,
                amount=split_value,
                currency=split_currency,
                fx_rate=None,
                tx_guid=tx.guid,
                split_guid=split.guid,
            )
            rows.append(row)
        return rows

    def _splits_to_transactions(
        self,
        splits_data: list,
        notes_map: dict[str, str],
        signed: bool,
    ) -> list[TransactionRow]:
        """Convert split data to TransactionRow objects."""
        tx_map = {}
        for split, tx, acc in splits_data:
            if tx.guid not in tx_map:
                tx_map[tx.guid] = {
                    "tx": tx,
                    "notes": notes_map.get(tx.guid),
                    "splits": [],
                }

            for s in tx.splits:
                split_acc = s.account
                split_value = Decimal(str(s.value))
                if not signed:
                    split_value = abs(split_value)

                tx_map[tx.guid]["splits"].append(
                    SplitRow(
                        date=tx.post_date,
                        description=tx.description,
                        account=split_acc.fullname,
                        memo=s.memo,
                        notes=tx_map[tx.guid]["notes"],
                        amount=split_value,
                        currency=(
                            split_acc.commodity.mnemonic
                            if split_acc.commodity
                            else ""
                        ),
                        fx_rate=None,
                        tx_guid=tx.guid,
                        split_guid=s.guid,
                    )
                )

        rows = []
        for guid, data in tx_map.items():
            seen = set()
            unique_splits = []
            for s in data["splits"]:
                if s.split_guid not in seen:
                    seen.add(s.split_guid)
                    unique_splits.append(s)

            rows.append(
                TransactionRow(
                    tx_guid=guid,
                    date=data["tx"].post_date,
                    description=data["tx"].description,
                    notes=data["notes"],
                    splits=unique_splits,
                )
            )
        return rows

    def _sort_rows(
        self, rows: list[SplitRow], sort_key: str, reverse: bool
    ) -> list[SplitRow]:
        """Sort split rows by the specified key."""
        key_map = {
            "date": lambda r: r.date,
            "amount": lambda r: r.amount,
            "account": lambda r: r.account,
            "description": lambda r: r.description,
        }
        key_fn = key_map.get(sort_key, key_map["date"])
        return sorted(rows, key=key_fn, reverse=reverse)


def run_repl(config: Config) -> int:
    """
    Run the interactive REPL.

    Args:
        config: gcg configuration

    Returns:
        Exit code
    """
    session = ReplSession(config)
    session.setup_readline()

    print("gcg interactive mode. Type 'help' for commands, 'quit' to exit.")

    # Auto-open book if path is configured
    try:
        session.open_book()
    except Exception:
        print("(No book loaded. Use 'open PATH' to load one.)")

    try:
        while session.running:
            try:
                prompt = "gcg> " if session.book else "gcg (no book)> "
                line = input(prompt)
                session.run_command(line)
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print()
                continue

    finally:
        session.save_history()
        session.close_book()

    return 0
