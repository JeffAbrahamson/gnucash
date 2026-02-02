# gcg - GnuCash Grep

A read-only command-line tool for searching and reporting from GnuCash SQLite books.

## Features

- **Search accounts** by name pattern (substring or regex)
- **Grep splits/transactions** by text in description, memo, or notes
- **Display ledgers** for specific accounts with filters
- **Multi-currency support** with automatic conversion using price database
- **Multiple output formats**: table, CSV, JSON
- **Interactive REPL** with readline support
- **Optional sidecar cache** for faster repeated searches

## Installation

```bash
# From PyPI
pip install gcg

# From source
pip install -e .

# With REPL enhancements
pip install gcg[repl]

# For development
pip install -e ".[dev]"
```

## Quick Start

```bash
# Search accounts
gcg accounts "Bank"
gcg accounts --regex "^Expenses:.*(Food|Restaurant)"

# Search transactions
gcg grep "amazon" --after 2025-01-01
gcg grep --regex "(insurance|mutuelle)" --amount 10..200

# Display ledger
gcg ledger "Assets:Bank:UK"
gcg ledger "Expenses:Amazon" --currency base --also-original

# View specific transaction/split
gcg tx abc123-guid
gcg split def456-guid

# Diagnostics
gcg doctor

# Interactive mode
gcg -i
```

## Commands

### gcg accounts PATTERN

Search accounts by name pattern.

```
Options:
  --regex           Treat PATTERN as regex
  --case-sensitive  Case-sensitive matching (default: insensitive)
  --tree            Render as account tree
  --tree-prune      Show tree pruned to matching paths
  --max-depth N     Limit tree depth
  --show-guids      Include account GUIDs
```

### gcg grep TEXT

Search splits/transactions for text.

```
Options:
  --regex           TEXT is a regular expression
  --case-sensitive  Case-sensitive matching
  --in FIELDS       Fields to search: desc,memo,notes (default: all)
  --account PAT     Restrict to accounts matching pattern
  --account-regex   Account pattern is regex
  --no-subtree      Don't include descendant accounts
  --after DATE      Posted on or after date (inclusive)
  --before DATE     Posted before date (exclusive)
  --date A..B       Date range (inclusive both ends)
  --amount MIN..MAX Amount filter (e.g., 10..100, ..50, 100..)
  --signed          Use signed amounts (default: absolute)
  --full-tx         Show full transactions containing matches
  --dedupe tx|split Deduplication mode
  --context MODE    For --full-tx: balanced or full
```

### gcg ledger ACCOUNT_PATTERN

Display a ledger for accounts.

```
Options:
  --account-regex   Account pattern is regex
  --no-subtree      Don't include descendant accounts
  --after DATE      Posted on or after date
  --before DATE     Posted before date
  --date A..B       Date range
  --amount MIN..MAX Amount filter
  --signed          Use signed amounts
```

### gcg tx GUID / gcg split GUID

Display a specific transaction or split by GUID.

### gcg doctor

Print diagnostic information about the configuration and book.

### gcg cache build|status|drop

Manage the optional sidecar cache.

```bash
gcg cache status     # Show cache info
gcg cache build      # Build cache from book
gcg cache build --force  # Rebuild cache
gcg cache drop       # Delete cache
```

## Global Options

```
-i, --interactive   Start REPL mode
--book PATH         Path to GnuCash SQLite file
--format FMT        Output format: table, csv, json
--no-header         Omit header row
--sort KEY          Sort by: date, amount, account, description
--reverse           Reverse sort order
--limit N           Limit output rows
--offset N          Skip first N rows
```

## Currency Options

These options are available for `grep` and `ledger` commands:

```
--currency MODE     Display mode: auto, base, split, account
--base-currency CUR Base currency for conversions (default: EUR)
--also-original     Show original amounts alongside converted
--fx-lookback DAYS  Max days to look back for exchange rates
```

### Currency Modes

- **auto** (default): Automatically choose based on context
- **base**: Always display in base currency when possible
- **split**: Display each split in its original currency
- **account**: Display in the account's commodity

## Configuration

### Book Location

The book path is resolved in order:

1. `--book PATH` command-line argument
2. `GCG_BOOK` environment variable
3. Config file: `~/.config/gcg/config.toml`
4. Default: `~/work/finance/gnucash/current/compta-perso.gnucash`

### Config File

Create `~/.config/gcg/config.toml`:

```toml
book = "/path/to/your/gnucash/file.gnucash"

[currency]
base = "EUR"
fx_lookback_days = 30
mode = "auto"

[output]
format = "table"
header = true

[cache]
enabled = true
path = "~/.cache/gcg/cache.sqlite"
```

## Date Semantics

- `--after` is **inclusive**: matches dates >= given date
- `--before` is **exclusive**: matches dates < given date
- `--date A..B` is **inclusive** on both ends

Examples:
```bash
# January 2026
gcg grep "amazon" --after 2026-01-01 --before 2026-02-01
gcg grep "amazon" --date 2026-01-01..2026-01-31

# From a date onwards
gcg grep "amazon" --date 2026-01-01..

# Up to a date
gcg grep "amazon" --date ..2026-01-31
```

## Amount Semantics

- Default: **absolute** amounts for both filtering and display
- `--signed`: Use signed values

Amount ranges:
```bash
--amount 10..100   # Between 10 and 100
--amount 100..     # 100 or more
--amount ..50      # 50 or less
```

## Interactive Mode (REPL)

Start with `gcg -i` or `gcg repl`:

```
gcg> open ~/path/to/book.gnucash
gcg> set currency auto
gcg> grep amazon --after 2025-01-01 --amount 5..200
gcg> ledger Assets:Bank:UK --currency account
gcg> quit
```

REPL commands:
- `open [PATH]` - Open a book
- `accounts`, `grep`, `ledger`, `tx`, `split` - Same as CLI
- `set format table|csv|json` - Change output format
- `set currency auto|base|split|account` - Change currency mode
- `set base-currency CUR` - Change base currency
- `help` - Show help
- `quit` / `exit` - Exit

History is saved to `~/.local/state/gcg/history`.

## Exit Codes

- `0` - Success (matches found or command completed)
- `1` - No matches found / GUID not found
- `2` - Error (invalid arguments, regex error, DB open failure)

## Safety

gcg is **read-only** and will never modify your GnuCash book:

- Opens SQLite in read-only mode
- Never creates journal or lock files
- The sidecar cache is stored separately

## Development

### Setting Up a Development Environment

```bash
# Clone the repository
git clone https://github.com/example/gcg.git
cd gcg

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_cli.py

# Run with coverage report
pytest --cov=gcg --cov-report=term-missing
```

### Code Quality

```bash
# Check formatting (must pass for CI)
black --check --line-length 79 gcg/ tests/
flake8 gcg/ tests/

# Auto-format code
black --line-length 79 gcg/ tests/
```

### Running Locally Without Installing

You can run gcg directly from the source directory without publishing to PyPI:

```bash
# Option 1: Use pip install -e (editable/development mode)
# After running this once, the 'gcg' command is available
pip install -e .
gcg --help

# Option 2: Run as a Python module
python -m gcg --help
python -m gcg accounts "Bank"
python -m gcg grep "amazon" --after 2025-01-01

# Option 3: Run the CLI directly
python gcg/cli.py --help
```

### Project Structure

```
gcg/
├── gcg/                 # Main package
│   ├── __init__.py
│   ├── __main__.py      # Allows `python -m gcg`
│   ├── cli.py           # Command-line interface
│   ├── book.py          # GnuCash book access
│   ├── cache.py         # Sidecar cache management
│   ├── config.py        # Configuration handling
│   ├── currency.py      # Currency conversion
│   ├── output.py        # Output formatting
│   └── repl.py          # Interactive REPL
├── tests/               # Test suite
│   ├── conftest.py      # Pytest fixtures
│   ├── test_cli.py
│   ├── test_config.py
│   ├── test_currency.py
│   ├── test_integration.py
│   └── test_output.py
├── pyproject.toml       # Package configuration
└── README.md
```

### Testing with a Real GnuCash Book

Set the `GCG_BOOK` environment variable to point to your GnuCash file:

```bash
export GCG_BOOK=~/path/to/your/book.gnucash
gcg doctor  # Verify it can open the book
gcg accounts ""  # List all accounts
```

## License

MIT License
