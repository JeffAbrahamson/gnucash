"""
Interactive REPL mode for gcg.

Provides a readline-enabled interactive shell for querying
GnuCash books without repeatedly loading them.
"""

import readline
import shlex
import sys
from pathlib import Path
from typing import Optional

from gcg.book import BookOpenError, open_gnucash_book
from gcg.config import Config, get_xdg_state_home


class ReplSession:
    """
    Interactive REPL session for gcg.

    Maintains state between commands and provides readline support
    with command history.
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
        if self.book is not None:
            # Close existing book
            self.book.close()
            self.book = None
            self.book_info = None

        book_path = (
            Path(path).expanduser().resolve()
            if path
            else self.config.resolve_book_path()
        )

        try:
            # We need to manage the context manually for REPL
            # since we want to keep the book open across commands
            ctx = open_gnucash_book(book_path)
            self.book, self.book_info = ctx.__enter__()
            # Store context for cleanup
            self._book_ctx = ctx
            print(f"Opened: {book_path}")
            print(f"  Accounts: {self.book_info.account_count}")
            print(f"  Transactions: {self.book_info.transaction_count}")
            return True

        except BookOpenError as e:
            print(f"Error: {e}", file=sys.stderr)
            return False

    def close_book(self) -> None:
        """Close the current book if open."""
        if self.book is not None:
            self._book_ctx.__exit__(None, None, None)
            self.book = None
            self.book_info = None

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
        """Handle the 'accounts' command in REPL."""
        # Build argv for CLI parser
        argv = ["accounts"] + args
        argv.extend(["--format", self.output_format])
        self._run_cli_command(argv)

    def cmd_grep(self, args: list[str]) -> None:
        """Handle the 'grep' command in REPL."""
        if not args:
            print("Usage: grep TEXT [OPTIONS]", file=sys.stderr)
            return

        argv = ["grep"] + args
        argv.extend(["--format", self.output_format])
        argv.extend(["--currency", self.currency_mode])
        argv.extend(["--base-currency", self.base_currency])
        self._run_cli_command(argv)

    def cmd_ledger(self, args: list[str]) -> None:
        """Handle the 'ledger' command in REPL."""
        if not args:
            print("Usage: ledger ACCOUNT_PATTERN [OPTIONS]", file=sys.stderr)
            return

        argv = ["ledger"] + args
        argv.extend(["--format", self.output_format])
        argv.extend(["--currency", self.currency_mode])
        argv.extend(["--base-currency", self.base_currency])
        self._run_cli_command(argv)

    def cmd_tx(self, args: list[str]) -> None:
        """Handle the 'tx' command in REPL."""
        if not args:
            print("Usage: tx GUID", file=sys.stderr)
            return

        argv = ["tx", args[0]]
        argv.extend(["--format", self.output_format])
        self._run_cli_command(argv)

    def cmd_split(self, args: list[str]) -> None:
        """Handle the 'split' command in REPL."""
        if not args:
            print("Usage: split GUID", file=sys.stderr)
            return

        argv = ["split", args[0]]
        argv.extend(["--format", self.output_format])
        self._run_cli_command(argv)

    def _run_cli_command(self, argv: list[str]) -> None:
        """
        Run a CLI command with the current book.

        This reuses the CLI parsing but operates on the already-open book.
        """
        from gcg.cli import create_parser

        parser = create_parser()

        try:
            args = parser.parse_args(argv)
        except SystemExit:
            # argparse calls sys.exit on error
            return

        # Execute command with current book
        # For now, we re-run through CLI which re-opens the book
        # A future optimization would reuse the open book
        from gcg.cli import (
            cmd_accounts,
            cmd_grep,
            cmd_ledger,
            cmd_tx,
            cmd_split,
        )

        cmd_map = {
            "accounts": cmd_accounts,
            "grep": cmd_grep,
            "ledger": cmd_ledger,
            "tx": cmd_tx,
            "split": cmd_split,
        }

        cmd_fn = cmd_map.get(args.command)
        if cmd_fn:
            cmd_fn(args, self.config)


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
