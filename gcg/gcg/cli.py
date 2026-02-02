"""
Command-line interface for gcg.

Provides the main entry point and argument parsing for all commands.
"""

import argparse
import re
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional

from gcg import __version__
from gcg.book import (
    BookOpenError,
    get_account_by_pattern,
    get_transaction_notes,
    open_gnucash_book,
)
from gcg.config import Config, load_config
from gcg.currency import (
    CurrencyConverter,
    determine_display_currency,
    get_account_currencies,
)
from gcg.output import (
    AccountRow,
    OutputFormatter,
    SplitRow,
    TransactionRow,
)


def parse_date(date_str: str) -> date:
    """Parse a date string in YYYY-MM-DD format."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"Invalid date format: {date_str}. Use YYYY-MM-DD."
        ) from e


def parse_date_range(range_str: str) -> tuple[Optional[date], Optional[date]]:
    """
    Parse a date range string like 'A..B', 'A..', or '..B'.

    Returns (start_date, end_date) where either may be None.
    For --date semantics, both start and end are inclusive.
    """
    if ".." not in range_str:
        raise argparse.ArgumentTypeError(
            f"Invalid date range: {range_str}. Use format A..B, A.., or ..B"
        )

    parts = range_str.split("..", 1)
    start_str, end_str = parts[0].strip(), parts[1].strip()

    start_date = parse_date(start_str) if start_str else None
    end_date = parse_date(end_str) if end_str else None

    return (start_date, end_date)


def parse_amount_range(
    range_str: str,
) -> tuple[Optional[Decimal], Optional[Decimal]]:
    """
    Parse an amount range string like 'MIN..MAX', 'MIN..', or '..MAX'.

    Returns (min_amount, max_amount) where either may be None.
    """
    if ".." not in range_str:
        raise argparse.ArgumentTypeError(
            f"Invalid amount range: {range_str}. "
            f"Use format MIN..MAX, MIN.., or ..MAX"
        )

    parts = range_str.split("..", 1)
    min_str, max_str = parts[0].strip(), parts[1].strip()

    try:
        min_amount = Decimal(min_str) if min_str else None
        max_amount = Decimal(max_str) if max_str else None
    except InvalidOperation as e:
        raise argparse.ArgumentTypeError(
            f"Invalid amount in range: {range_str}"
        ) from e

    return (min_amount, max_amount)


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser."""
    parser = argparse.ArgumentParser(
        prog="gcg",
        description="Grep-like search and reporting for GnuCash SQLite books",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Start interactive REPL mode",
    )
    parser.add_argument(
        "--book", metavar="PATH", help="Path to GnuCash SQLite file"
    )
    parser.add_argument(
        "--format",
        choices=["table", "csv", "json"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="Omit header row in table/CSV output",
    )
    parser.add_argument(
        "--fields",
        metavar="LIST",
        help="Comma-separated list of fields to display",
    )
    parser.add_argument(
        "--sort",
        choices=["date", "amount", "account", "description"],
        default="date",
        help="Sort key (default: date)",
    )
    parser.add_argument(
        "--reverse", action="store_true", help="Reverse sort order"
    )
    parser.add_argument(
        "--limit", type=int, metavar="N", help="Limit output to N rows"
    )
    parser.add_argument(
        "--offset", type=int, metavar="N", help="Skip first N rows"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # accounts command
    accounts_parser = subparsers.add_parser(
        "accounts", help="Search accounts by pattern"
    )
    accounts_parser.add_argument(
        "pattern",
        nargs="?",
        default="",
        help="Account name pattern (substring match by default)",
    )
    accounts_parser.add_argument(
        "--regex", action="store_true", help="Treat pattern as regex"
    )
    accounts_parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Use case-sensitive matching",
    )
    accounts_parser.add_argument(
        "--tree", action="store_true", help="Render as account tree"
    )
    accounts_parser.add_argument(
        "--tree-prune",
        action="store_true",
        help="Show tree pruned to matching paths with full subtrees",
    )
    accounts_parser.add_argument(
        "--max-depth", type=int, metavar="N", help="Limit tree depth"
    )
    accounts_parser.add_argument(
        "--show-guids",
        action="store_true",
        help="Include account GUIDs in output",
    )

    # grep command
    grep_parser = subparsers.add_parser(
        "grep", help="Search splits/transactions for text"
    )
    grep_parser.add_argument("text", help="Text to search for")
    grep_parser.add_argument(
        "--regex", action="store_true", help="Treat text as regex"
    )
    grep_parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Use case-sensitive matching",
    )
    grep_parser.add_argument(
        "--in",
        dest="search_fields",
        default="desc,memo,notes",
        help="Fields to search: desc,memo,notes (default: all)",
    )
    grep_parser.add_argument(
        "--account",
        metavar="PATTERN",
        help="Restrict to accounts matching pattern",
    )
    grep_parser.add_argument(
        "--account-regex", action="store_true", help="Account pattern is regex"
    )
    grep_parser.add_argument(
        "--no-subtree",
        action="store_true",
        help="Don't include descendant accounts",
    )
    grep_parser.add_argument(
        "--after",
        type=parse_date,
        metavar="YYYY-MM-DD",
        help="Filter: posted on or after date (inclusive)",
    )
    grep_parser.add_argument(
        "--before",
        type=parse_date,
        metavar="YYYY-MM-DD",
        help="Filter: posted before date (exclusive)",
    )
    grep_parser.add_argument(
        "--date",
        type=parse_date_range,
        metavar="A..B",
        help="Date range (inclusive both ends)",
    )
    grep_parser.add_argument(
        "--amount",
        type=parse_amount_range,
        metavar="MIN..MAX",
        help="Amount range filter",
    )
    grep_parser.add_argument(
        "--signed",
        action="store_true",
        help="Use signed amounts (default: absolute)",
    )
    grep_parser.add_argument(
        "--full-tx",
        action="store_true",
        help="Show full transactions containing matches",
    )
    grep_parser.add_argument(
        "--dedupe",
        choices=["tx", "split"],
        default="split",
        help="Deduplication mode (default: split)",
    )
    grep_parser.add_argument(
        "--context",
        choices=["balanced", "full"],
        default="full",
        help="Context mode for --full-tx (default: full)",
    )
    _add_currency_args(grep_parser)

    # ledger command
    ledger_parser = subparsers.add_parser(
        "ledger", help="Display ledger for accounts"
    )
    ledger_parser.add_argument("account_pattern", help="Account name pattern")
    ledger_parser.add_argument(
        "--account-regex", action="store_true", help="Account pattern is regex"
    )
    ledger_parser.add_argument(
        "--no-subtree",
        action="store_true",
        help="Don't include descendant accounts",
    )
    ledger_parser.add_argument(
        "--after",
        type=parse_date,
        metavar="YYYY-MM-DD",
        help="Filter: posted on or after date",
    )
    ledger_parser.add_argument(
        "--before",
        type=parse_date,
        metavar="YYYY-MM-DD",
        help="Filter: posted before date",
    )
    ledger_parser.add_argument(
        "--date", type=parse_date_range, metavar="A..B", help="Date range"
    )
    ledger_parser.add_argument(
        "--amount",
        type=parse_amount_range,
        metavar="MIN..MAX",
        help="Amount range filter",
    )
    ledger_parser.add_argument(
        "--signed", action="store_true", help="Use signed amounts"
    )
    _add_currency_args(ledger_parser)

    # tx command
    tx_parser = subparsers.add_parser("tx", help="Display transaction by GUID")
    tx_parser.add_argument("guid", help="Transaction GUID")

    # split command
    split_parser = subparsers.add_parser("split", help="Display split by GUID")
    split_parser.add_argument("guid", help="Split GUID")

    # doctor command
    subparsers.add_parser("doctor", help="Print diagnostic info")

    # cache command
    cache_parser = subparsers.add_parser("cache", help="Manage sidecar cache")
    cache_parser.add_argument(
        "action", choices=["build", "status", "drop"], help="Cache action"
    )
    cache_parser.add_argument(
        "--force", action="store_true", help="Force rebuild cache"
    )

    # repl command (alternative to -i)
    subparsers.add_parser("repl", help="Start interactive REPL mode")

    return parser


def _add_currency_args(parser: argparse.ArgumentParser) -> None:
    """Add currency-related arguments to a parser."""
    parser.add_argument(
        "--currency",
        choices=["auto", "base", "split", "account"],
        default="auto",
        help="Currency display mode (default: auto)",
    )
    parser.add_argument(
        "--base-currency",
        metavar="CUR",
        help="Base currency for conversions (default: EUR)",
    )
    parser.add_argument(
        "--also-original",
        action="store_true",
        help="Show original currency alongside converted",
    )
    parser.add_argument(
        "--fx-lookback",
        type=int,
        metavar="DAYS",
        help="Max days to look back for exchange rates",
    )


def resolve_date_filters(args) -> tuple[Optional[date], Optional[date]]:
    """
    Resolve date filters from --after/--before/--date args.

    --after is inclusive, --before is exclusive.
    --date A..B is inclusive on both ends (converted to after/before).
    """
    after_date = getattr(args, "after", None)
    before_date = getattr(args, "before", None)
    date_range = getattr(args, "date", None)

    if date_range:
        range_start, range_end = date_range
        if range_start:
            after_date = range_start
        if range_end:
            # --date end is inclusive, so add 1 day for before
            before_date = range_end + timedelta(days=1)

    return (after_date, before_date)


def cmd_accounts(args, config: Config) -> int:
    """Handle the accounts command."""
    try:
        with open_gnucash_book(config.resolve_book_path()) as (book, info):
            accounts = get_account_by_pattern(
                book,
                args.pattern,
                is_regex=args.regex,
                case_sensitive=args.case_sensitive,
                include_subtree=(
                    not args.no_subtree
                    if hasattr(args, "no_subtree")
                    else True
                ),
            )

            if not accounts:
                return 1  # No matches

            # Sort accounts by full name
            accounts.sort(key=lambda a: a.fullname)

            # Convert to output rows
            rows = []
            for acc in accounts:
                depth = acc.fullname.count(":") if args.tree else 0
                rows.append(
                    AccountRow(
                        name=acc.fullname,
                        type=acc.type,
                        currency=(
                            acc.commodity.mnemonic if acc.commodity else ""
                        ),
                        guid=acc.guid if args.show_guids else None,
                        depth=depth,
                    )
                )

            # Apply limit/offset
            if args.offset:
                rows = rows[args.offset :]
            if args.limit:
                rows = rows[: args.limit]

            formatter = OutputFormatter(
                format_type=args.format,
                show_header=not args.no_header,
                show_guids=args.show_guids,
            )
            formatter.format_accounts(rows, tree_mode=args.tree)
            return 0

    except BookOpenError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


def cmd_grep(args, config: Config) -> int:
    """Handle the grep command."""
    # Compile search pattern
    flags = 0 if args.case_sensitive else re.IGNORECASE
    if args.regex:
        try:
            pattern = re.compile(args.text, flags)
        except re.error as e:
            print(f"Invalid regex: {e}", file=sys.stderr)
            return 2
    else:
        # Escape for literal match
        pattern = re.compile(re.escape(args.text), flags)

    # Parse search fields
    search_fields = set(args.search_fields.split(","))

    # Resolve date filters
    after_date, before_date = resolve_date_filters(args)

    # Amount range
    amount_range = args.amount if args.amount else (None, None)

    try:
        with open_gnucash_book(config.resolve_book_path()) as (book, info):
            # Filter accounts if specified
            if args.account:
                accounts = get_account_by_pattern(
                    book,
                    args.account,
                    is_regex=args.account_regex,
                    case_sensitive=False,
                    include_subtree=not args.no_subtree,
                )
                account_set = set(accounts)
            else:
                accounts = [
                    a
                    for a in book.accounts
                    if a.type not in ("ROOT", "TRADING")
                ]
                account_set = None

            # Check notes support
            notes_supported = info.has_notes_column or info.has_slots_notes
            if "notes" in search_fields and not notes_supported:
                print(
                    "Warning: Notes not supported in this book schema",
                    file=sys.stderr,
                )
                search_fields.discard("notes")

            # Collect matching splits
            matching_splits = []
            seen_tx_guids = set()

            for acc in accounts:
                for split in acc.splits:
                    tx = split.transaction

                    # Account filter
                    if account_set and split.account not in account_set:
                        continue

                    # Date filter
                    tx_date = tx.post_date
                    if after_date and tx_date < after_date:
                        continue
                    if before_date and tx_date >= before_date:
                        continue

                    # Amount filter
                    split_value = Decimal(str(split.value))
                    if not args.signed:
                        split_value = abs(split_value)
                    min_amt, max_amt = amount_range
                    if min_amt is not None and split_value < min_amt:
                        continue
                    if max_amt is not None and split_value > max_amt:
                        continue

                    # Text search
                    searchable = ""
                    if "desc" in search_fields:
                        searchable += tx.description + " "
                    if "memo" in search_fields:
                        searchable += (split.memo or "") + " "
                    if "notes" in search_fields and notes_supported:
                        notes = get_transaction_notes(
                            config.resolve_book_path(),
                            tx.guid,
                            info.has_notes_column,
                        )
                        if notes:
                            searchable += notes + " "

                    if not pattern.search(searchable):
                        continue

                    # Deduplication
                    if args.dedupe == "tx" or args.full_tx:
                        if tx.guid in seen_tx_guids:
                            continue
                        seen_tx_guids.add(tx.guid)

                    matching_splits.append((split, tx, acc))

            if not matching_splits:
                return 1  # No matches

            # Format output
            rows = _splits_to_rows(
                matching_splits,
                config,
                info,
                args,
            )

            # Sort
            rows = _sort_rows(rows, args.sort, args.reverse)

            # Limit/offset
            if args.offset:
                rows = rows[args.offset :]
            if args.limit:
                rows = rows[: args.limit]

            formatter = OutputFormatter(
                format_type=args.format,
                show_header=not args.no_header,
                include_notes="notes" in search_fields and notes_supported,
            )

            if args.full_tx:
                tx_rows = _splits_to_transactions(
                    matching_splits, config, info, args
                )
                formatter.format_transactions(tx_rows)
            else:
                formatter.format_splits(rows)

            return 0

    except BookOpenError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


def cmd_ledger(args, config: Config) -> int:
    """Handle the ledger command."""
    after_date, before_date = resolve_date_filters(args)
    amount_range = args.amount if args.amount else (None, None)

    try:
        with open_gnucash_book(config.resolve_book_path()) as (book, info):
            accounts = get_account_by_pattern(
                book,
                args.account_pattern,
                is_regex=args.account_regex,
                case_sensitive=False,
                include_subtree=not args.no_subtree,
            )

            if not accounts:
                print(
                    f"No accounts matching: {args.account_pattern}",
                    file=sys.stderr,
                )
                return 1

            splits_data = []

            for acc in accounts:
                for split in acc.splits:
                    tx = split.transaction

                    # Date filter
                    tx_date = tx.post_date
                    if after_date and tx_date < after_date:
                        continue
                    if before_date and tx_date >= before_date:
                        continue

                    # Amount filter
                    split_value = Decimal(str(split.value))
                    if not args.signed:
                        split_value = abs(split_value)
                    min_amt, max_amt = amount_range
                    if min_amt is not None and split_value < min_amt:
                        continue
                    if max_amt is not None and split_value > max_amt:
                        continue

                    splits_data.append((split, tx, acc))

            if not splits_data:
                return 1

            rows = _splits_to_rows(splits_data, config, info, args)
            rows = _sort_rows(rows, args.sort, args.reverse)

            if args.offset:
                rows = rows[args.offset :]
            if args.limit:
                rows = rows[: args.limit]

            formatter = OutputFormatter(
                format_type=args.format,
                show_header=not args.no_header,
            )
            formatter.format_splits(rows)
            return 0

    except BookOpenError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


def cmd_tx(args, config: Config) -> int:
    """Handle the tx command - show transaction by GUID."""
    try:
        with open_gnucash_book(config.resolve_book_path()) as (book, info):
            tx = None
            for t in book.transactions:
                if t.guid == args.guid:
                    tx = t
                    break

            if tx is None:
                print(f"Transaction not found: {args.guid}", file=sys.stderr)
                return 1

            # Get notes
            notes = get_transaction_notes(
                config.resolve_book_path(), tx.guid, info.has_notes_column
            )

            # Build split rows
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
                        currency=(
                            acc.commodity.mnemonic if acc.commodity else ""
                        ),
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

            formatter = OutputFormatter(
                format_type=args.format,
                show_header=not args.no_header,
            )
            formatter.format_transactions([tx_row])
            return 0

    except BookOpenError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


def cmd_split(args, config: Config) -> int:
    """Handle the split command - show split by GUID."""
    try:
        with open_gnucash_book(config.resolve_book_path()) as (book, info):
            found_split = None
            found_tx = None
            found_acc = None

            for acc in book.accounts:
                for split in acc.splits:
                    if split.guid == args.guid:
                        found_split = split
                        found_tx = split.transaction
                        found_acc = acc
                        break
                if found_split:
                    break

            if found_split is None:
                print(f"Split not found: {args.guid}", file=sys.stderr)
                return 1

            notes = get_transaction_notes(
                config.resolve_book_path(),
                found_tx.guid,
                info.has_notes_column,
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

            formatter = OutputFormatter(
                format_type=args.format,
                show_header=not args.no_header,
            )
            formatter.format_splits([row])
            return 0

    except BookOpenError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


def cmd_doctor(args, config: Config) -> int:
    """Handle the doctor command - print diagnostics."""
    print("gcg diagnostic information")
    print("=" * 40)
    print(f"Version: {__version__}")
    print()

    book_path = config.resolve_book_path()
    print(f"Book path: {book_path}")
    print(f"Book exists: {book_path.exists()}")

    if book_path.exists():
        try:
            with open_gnucash_book(book_path) as (book, info):
                print()
                print("Book info:")
                print(f"  Default currency: {info.default_currency}")
                print(f"  Account count: {info.account_count}")
                print(f"  Transaction count: {info.transaction_count}")
                print(f"  Notes column: {info.has_notes_column}")
                print(f"  Notes in slots: {info.has_slots_notes}")
        except BookOpenError as e:
            print(f"  Error opening: {e}")

    print()
    print("Configuration:")
    print(f"  Base currency: {config.base_currency}")
    print(f"  FX lookback days: {config.fx_lookback_days}")
    print(f"  Output format: {config.output_format}")
    print(f"  Cache path: {config.cache_path}")
    print(f"  Cache enabled: {config.cache_enabled}")

    print()
    print("Environment:")
    import os

    print(f"  GCG_BOOK: {os.environ.get('GCG_BOOK', '(not set)')}")

    return 0


def cmd_cache(args, config: Config) -> int:
    """Handle the cache command."""
    from gcg.cache import CacheManager

    cache_mgr = CacheManager(config.cache_path, config.resolve_book_path())

    if args.action == "status":
        status = cache_mgr.status()
        print(f"Cache path: {config.cache_path}")
        print(f"Cache exists: {status['exists']}")
        if status["exists"]:
            print(f"Cache size: {status['size_bytes']} bytes")
            print(f"Last modified: {status['modified']}")
            print(f"Split count: {status.get('split_count', 'unknown')}")
        return 0

    elif args.action == "build":
        print(f"Building cache at {config.cache_path}...")
        try:
            with open_gnucash_book(config.resolve_book_path()) as (book, info):
                cache_mgr.build(book, info, force=args.force)
            print("Cache built successfully.")
            return 0
        except BookOpenError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 2

    elif args.action == "drop":
        if cache_mgr.drop():
            print("Cache dropped.")
        else:
            print("No cache to drop.")
        return 0

    return 2


def _splits_to_rows(
    splits_data: list,
    config: Config,
    info,
    args,
) -> list[SplitRow]:
    """Convert split/tx/acc tuples to SplitRow objects."""
    rows = []
    converter = CurrencyConverter(
        config.resolve_book_path(),
        base_currency=getattr(args, "base_currency", None)
        or config.base_currency,
        lookback_days=getattr(args, "fx_lookback", None)
        or config.fx_lookback_days,
    )

    currency_mode = getattr(args, "currency", "auto")
    also_original = getattr(args, "also_original", False)
    signed = getattr(args, "signed", False)

    # Determine target currency
    account_currencies = get_account_currencies(
        [acc for _, _, acc in splits_data]
    )
    target_currency = determine_display_currency(
        currency_mode,
        [s for s, _, _ in splits_data],
        account_currencies,
        config.base_currency,
    )

    for split, tx, acc in splits_data:
        split_value = Decimal(str(split.value))
        if not signed:
            split_value = abs(split_value)

        split_currency = acc.commodity.mnemonic if acc.commodity else "???"

        # Currency conversion
        if target_currency and target_currency != split_currency:
            result = converter.convert(
                split_value,
                split_currency,
                target_currency,
                tx.post_date,
            )
            display_amount = result.amount
            display_currency = result.currency
            fx_rate = result.fx_rate if result.converted else None
        else:
            display_amount = split_value
            display_currency = split_currency
            fx_rate = None

        # Get notes if available
        notes = None
        if info.has_notes_column or info.has_slots_notes:
            notes = get_transaction_notes(
                config.resolve_book_path(), tx.guid, info.has_notes_column
            )

        row = SplitRow(
            date=tx.post_date,
            description=tx.description,
            account=acc.fullname,
            memo=split.memo,
            notes=notes,
            amount=display_amount,
            currency=display_currency,
            fx_rate=fx_rate,
            tx_guid=tx.guid,
            split_guid=split.guid,
        )

        if also_original and fx_rate:
            row.amount_orig = split_value
            row.currency_orig = split_currency

        rows.append(row)

    return rows


def _splits_to_transactions(
    splits_data: list,
    config: Config,
    info,
    args,
) -> list[TransactionRow]:
    """Convert split data to TransactionRow objects (for --full-tx)."""
    # Group by transaction
    tx_map = {}
    for split, tx, acc in splits_data:
        if tx.guid not in tx_map:
            notes = None
            if info.has_notes_column or info.has_slots_notes:
                notes = get_transaction_notes(
                    config.resolve_book_path(), tx.guid, info.has_notes_column
                )
            tx_map[tx.guid] = {
                "tx": tx,
                "notes": notes,
                "splits": [],
            }

        # Add all splits of the transaction
        for s in tx.splits:
            split_acc = s.account
            split_value = Decimal(str(s.value))
            if not getattr(args, "signed", False):
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
        # Dedupe splits by guid
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
    rows: list[SplitRow], sort_key: str, reverse: bool
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


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    # Load config with CLI overrides
    config = load_config(
        book_path=args.book,
        output_format=args.format,
        show_header=not args.no_header,
    )

    # Handle interactive mode
    if args.interactive or args.command == "repl":
        from gcg.repl import run_repl

        return run_repl(config)

    # Handle commands
    if args.command == "accounts":
        return cmd_accounts(args, config)
    elif args.command == "grep":
        return cmd_grep(args, config)
    elif args.command == "ledger":
        return cmd_ledger(args, config)
    elif args.command == "tx":
        return cmd_tx(args, config)
    elif args.command == "split":
        return cmd_split(args, config)
    elif args.command == "doctor":
        return cmd_doctor(args, config)
    elif args.command == "cache":
        return cmd_cache(args, config)
    elif args.command is None:
        parser.print_help()
        return 0
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
