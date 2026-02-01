# SPEC.md — `gcg`: grep-like search/reporting for GnuCash (SQLite)

`gcg` is a read-only command-line program that opens a GnuCash book stored in SQLite and provides grep/ledger-style search and reporting. It is designed to be:
- **Fast enough for interactive use** (optional sidecar cache).
- **Pipeline-friendly** (stable identifiers, CSV/JSON output, grep-like exit codes).
- **Safe** (never writes to the GnuCash book; opens SQLite read-only when possible).

Primary implementation language: **Python**. Preferred library: **piekash** for book opening and object mapping, with **direct SQL** (or a sidecar cache) for high-throughput searches.

---

## 1. Goals and non-goals

### Goals
- Search accounts by name/code pattern.
- Search transactions/splits by text (description, memo, notes) with optional regex.
- Filter results by posted date range and amount range.
- Display either:
  - matching **splits** (default), or
  - full **transactions** containing any matching splits (deduped).
- Support multi-currency books with configurable currency display behavior.
- Provide non-interactive CLI and an interactive REPL with readline support.
- Output as human table, CSV, or JSON.

### Non-goals
- Editing/writing to the GnuCash book (no write operations).
- Reconciliation workflows or posting new transactions.
- Full accounting reports (balance sheet, P&L) beyond simple ledgers/filters (can be added later).

---

## 2. Terminology (GnuCash)

- **Book**: the GnuCash dataset stored in SQLite.
- **Account**: hierarchical node (e.g., `Assets:Bank:UK`).
- **Transaction (tx)**: a dated entry with description; contains multiple splits.
- **Split**: one line of a transaction affecting a specific account, with an amount/value and optional memo.

`gcg` returns **split rows** by default (grep-like) and can expand to full **transaction blocks**.

---

## 3. Book location and configuration

### Default book path
Default path is:

`$HOME/work/finance/gnucash/current/compta-perso.gnucash`

### Override precedence
1. `--book PATH`
2. `GCG_BOOK` environment variable
3. XDG config file: `${XDG_CONFIG_HOME:-$HOME/.config}/gcg/config.toml`
4. built-in default above

### Read-only open
Open SQLite using read-only mode when possible (SQLite URI `file:...?...mode=ro`). If read-only open fails, fallback to normal read with a warning, but still never write.

---

## 4. Command-line interface

Top-level:

```
gcg [--book PATH] [--format table|csv|json] [--no-header] [--fields LIST]
    [--sort KEY] [--reverse] [--limit N] [--offset N]
    <command> [command options...]
```

### 4.1 Commands

#### `gcg accounts PATTERN`
Search accounts by pattern (substring by default).

Options:
- `--regex` : treat PATTERN as regex
- `--case-sensitive` : default is case-insensitive
- `--tree` : render the account tree with matches
- `--tree-prune` : show tree from root pruned to matching paths, then full subtrees below matches
- `--max-depth N` : limit depth in tree views
- `--show-guids` : include account GUIDs in output

Default output: list of matching accounts (one per row).

#### `gcg grep TEXT`
Search splits/transactions for TEXT in selected fields.

Options:
- `--regex` : TEXT is a regular expression
- `--case-sensitive` : default case-insensitive
- `--in desc,memo,notes` : which fields to search (default: `desc,memo,notes` if notes exist; otherwise `desc,memo`)
- `--account ACCOUNT_PATTERN` : restrict to accounts whose full name matches pattern
- `--account-regex` : account pattern is regex
- `--no-subtree` : by default, `--account` matches include all descendant accounts
- `--after YYYY-MM-DD` / `--before YYYY-MM-DD` : posted date filter (inclusive/exclusive rules below)
- `--date YYYY-MM-DD..YYYY-MM-DD` : alternative range syntax
- `--amount MIN..MAX` : amount filter (applies to split amount/value; default absolute)
- `--signed` : interpret amount filters and display using signed values (default: absolute)
- `--full-tx` : show full transactions containing matching splits (dedupe by tx GUID)
- `--dedupe tx|split` : default `split`, but forced to `tx` when `--full-tx`
- `--context balanced|full` : when `--full-tx`, choose:
  - `full`: all splits
  - `balanced`: only matching splits plus the minimal set of counter-splits to balance

#### `gcg ledger ACCOUNT_PATTERN`
Display a ledger (split list) for one or more accounts.

Options:
- same date/amount filters as `grep`
- `--group-by day|month|payee` (optional, future)
- `--account-regex`, `--no-subtree`

Default output: splits for accounts in posted date order.

#### `gcg tx GUID` / `gcg split GUID`
Display a specific transaction or split by GUID.

#### `gcg doctor`
Print diagnostic info: resolved book path, open mode, schema/version hints, piecash version, cache status, default currency rules.

#### `gcg cache build|status|drop`
Manage an optional **sidecar cache database** (separate SQLite file). Never modifies the GnuCash DB.

---

## 5. Matching semantics

### Case sensitivity
- Default: **case-insensitive** matching.
- `--case-sensitive` toggles.

### Regex
- When `--regex` is set, use Python `re` with Unicode enabled.
- Invalid regex yields exit code 2 and a clear error message.

### Field selection for `grep`
- `desc`: transaction description
- `memo`: split memo
- `notes`: transaction notes (if present in schema)

If `notes` is not present, it is ignored with a warning (but not an error).

---

## 6. Date semantics

- Date filters apply to **posted date** (transaction date).
- Inputs are ISO `YYYY-MM-DD` in local time.
- `--after` is **inclusive**; `--before` is **exclusive** (mirrors many CLI tools).
  - Example: `--after 2026-01-01 --before 2026-02-01` selects January 2026.
- `--date A..B` is equivalent to `--after A --before (B + 1 day)` only if explicitly specified; otherwise it follows the same inclusive/exclusive semantics as above (implementation must document exact behavior).

---

## 7. Amount semantics

### Signed vs absolute
- Default: **absolute amount** for both filtering and display, for sanity across account types and sign conventions.
- `--signed` enables signed values and signed filtering.

### Amount source
Define precisely which numeric to use for filters and display:
- Use **split value** in the split’s commodity/currency (GnuCash “value”), not quantity, unless an account commodity requires quantity (future flag).
- For ledgers, value is the default.

### Ranges
- `--amount MIN..MAX` where either side may be omitted:
  - `..100` (≤ 100)
  - `10..` (≥ 10)
  - `10..100`

---

## 8. Multi-currency display and conversion

The book contains multiple currencies/commodities. `gcg` must provide a predictable mechanism to choose the display currency and optionally show original amounts.

### 8.1 Key concepts
- Each split has a **native commodity** (currency) and an amount/value in that commodity.
- The book may contain **price quotes** (“prices”) enabling conversion between commodities on or near dates.

### 8.2 Display currency modes
`--currency MODE` controls what currency to display:

- `auto` (default):
  1. If an **account filter** is used (e.g., `ledger` or `grep --account ...`) and all selected accounts share a single commodity, display in that commodity.
  2. Else if all matched splits share a single currency, display in that currency.
  3. Else if the configured **base currency** is set (default `EUR`), display in base currency *when conversion is possible*; otherwise fall back to split currency per row.
- `base` : always display in base currency when conversion is possible; otherwise fall back to original.
- `split` : always display the split’s original currency (no conversion).
- `account` : display using the account commodity when defined; otherwise split currency.

Base currency:
- default: `EUR`
- configurable via `--base-currency EUR` or config file.

### 8.3 Showing original amounts alongside converted
`--also-original` adds columns for the original currency and amount in addition to the chosen display currency.

Example (table fields):
- `amount_display`, `ccy_display`
- `amount_orig`, `ccy_orig`

This supports cases like:
- ledger for a UK bank account in **GBP** (account currency),
- while still optionally showing original vendor currency when relevant.

### 8.4 Conversion rules
When conversion is required:
- Use the book’s **price database** (GnuCash prices) to compute a rate for `from_ccy -> to_ccy` on the tx posted date.
- If there is no exact rate on that date:
  - choose the **most recent prior** price (<= date) within a configurable lookback window (default 30 days),
  - otherwise fail conversion for that row.

If conversion fails:
- In `auto`/`base`/`account` modes, fall back to original currency and mark conversion as missing (e.g., `rate = null`, `ccy_display = ccy_orig`), and optionally emit a warning summary.
- In `--strict-currency` mode (future), missing conversion becomes an error (exit code 2).

### 8.5 Rounding/precision
- Internally use `Decimal`.
- Display with currency-appropriate precision if known; otherwise 2 decimals.
- JSON/CSV outputs should include both raw decimal string and currency code.

---

## 9. Output formats

### 9.1 Common columns
Default split-row output fields (table/CSV/JSON):
- `date` (posted)
- `description`
- `account` (full name)
- `memo` (if available)
- `notes` (if available and selected)
- `amount` + `currency` (per currency mode)
- `tx_guid`, `split_guid`

Optional:
- `account_guid`
- `value_orig`, `currency_orig` when `--also-original`

### 9.2 Table output
Use a simple tabular renderer (e.g., `tabulate` or `tabular.tabular`) with:
- stable column order
- header on by default; `--no-header` disables

### 9.3 CSV output
- RFC4180-ish, UTF-8, newline `\n`
- header included unless `--no-header`

### 9.4 JSON output
Two shapes:
- Default: JSON array of objects.
- When `--full-tx`: array of tx objects:
  - `{ "tx_guid": ..., "date": ..., "description": ..., "splits": [ ... ] }`

---

## 10. Sorting, limiting, exit codes

### Sorting
`--sort` keys:
- `date` (default), `amount`, `account`, `description`
`--reverse` reverses.

### Pagination
- `--limit N`, `--offset N` available for all list-producing commands.

### Exit codes
- `0` : at least one match/row produced
- `1` : no matches
- `2` : error (invalid args, regex error, DB open failure, etc.)

---

## 11. Interactive mode (REPL)

### Invocation
- `gcg -i` or `gcg repl`

### Behavior
- Uses `readline` (or `prompt_toolkit` if available) for history and editing.
- Loads the book once per session.
- Commands map directly to CLI commands; the REPL parses a line into the same argument parser.

### REPL commands (minimum)
- `open PATH` : open a different book
- `accounts ...` : same syntax as CLI `accounts`
- `grep ...`
- `ledger ...`
- `tx GUID`
- `split GUID`
- `set format table|csv|json`
- `set currency auto|base|split|account`
- `set base-currency EUR`
- `help`, `quit`

History file:
- `${XDG_STATE_HOME:-$HOME/.local/state}/gcg/history`

---

## 12. Sidecar cache (optional but recommended)

### Motivation
Direct SQL against the GnuCash schema can still be slow for repeated grep-like queries. A sidecar cache provides:
- denormalized rows (split + tx + account full name)
- precomputed lowercase search fields
- optional FTS5 index for fast substring queries (implementation-dependent)

### Location
Default:
`${XDG_CACHE_HOME:-$HOME/.cache}/gcg/cache.sqlite`

### Commands
- `gcg cache build [--force]`
- `gcg cache status`
- `gcg cache drop`

The cache is **never** the GnuCash DB and may be rebuilt at any time.

---

## 13. Implementation notes (non-normative)

- Prefer piecash for book open + account tree. For grep/ledger:
  - either query GnuCash tables directly, or
  - query the sidecar cache if present and enabled.
- Use `Decimal` everywhere for amounts.
- Ensure deterministic ordering and stable formatting for testability.
- Provide unit tests for parsing/range logic and integration tests against a small fixture book.

---

## 14. Examples

Account lookup:
```
gcg accounts "512" 
gcg accounts --regex '^Expenses:.*(Food|Restaurant)' --tree --tree-prune
```

Grep:
```
gcg grep "amazon" --after 2025-01-01 --before 2026-01-01
gcg grep -i "tesco" --full-tx --dedupe tx
gcg grep --regex '(assurance|mutuelle)' --amount 10..200 --currency base --also-original
```

Ledger:
```
gcg ledger "Assets:Bank:UK" --currency account
gcg ledger "Expenses:Amazon" --currency base --also-original
```

Interactive:
```
gcg -i
> open ~/work/finance/gnucash/current/compta-perso.gnucash
> set currency auto
> grep amazon --after 2025-01-01 --amount 5..200
> ledger Assets:Bank:UK --currency account
```

---

## 15. Open questions (to decide before coding)

1. Exact mapping of “notes” in your SQLite schema/version (tx notes vs slot table). If notes live in slots, decide whether `--in notes` is supported by default or only via cache.
2. Conversion rate lookup strategy:
   - allow forward lookup if no prior rate?
   - lookback window length?
3. For accounts with non-currency commodities (e.g., stocks), whether `ledger` should display quantity vs value (future flag: `--quantity`).
