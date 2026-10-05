"""Tests for CLI argument parsing and date/amount range handling."""

import argparse
from datetime import date
from decimal import Decimal

import pytest

# Skip all tests if piecash is not available (required by gcg.cli)
pytest.importorskip("piecash")


class TestDateParsing:
    """Tests for date parsing functions."""

    def test_parse_date_valid(self):
        """Valid date string should parse correctly."""
        from gcg.cli import parse_date

        result = parse_date("2026-01-15")
        assert result == date(2026, 1, 15)

    def test_parse_date_invalid_format(self):
        """Invalid date format should raise ArgumentTypeError."""
        from gcg.cli import parse_date

        with pytest.raises(argparse.ArgumentTypeError):
            parse_date("01-15-2026")

    def test_parse_date_invalid_date(self):
        """Invalid date value should raise ArgumentTypeError."""
        from gcg.cli import parse_date

        with pytest.raises(argparse.ArgumentTypeError):
            parse_date("2026-13-01")  # Invalid month


class TestDateRangeParsing:
    """Tests for date range parsing."""

    def test_parse_date_range_full(self):
        """Full date range A..B should parse both dates."""
        from gcg.cli import parse_date_range

        start, end = parse_date_range("2026-01-01..2026-01-31")
        assert start == date(2026, 1, 1)
        assert end == date(2026, 1, 31)

    def test_parse_date_range_open_end(self):
        """Open-ended range A.. should have None end."""
        from gcg.cli import parse_date_range

        start, end = parse_date_range("2026-01-01..")
        assert start == date(2026, 1, 1)
        assert end is None

    def test_parse_date_range_open_start(self):
        """Open-start range ..B should have None start."""
        from gcg.cli import parse_date_range

        start, end = parse_date_range("..2026-01-31")
        assert start is None
        assert end == date(2026, 1, 31)

    def test_parse_date_range_no_dots(self):
        """Range without .. should raise error."""
        from gcg.cli import parse_date_range

        with pytest.raises(argparse.ArgumentTypeError):
            parse_date_range("2026-01-01")

    def test_parse_date_range_whitespace(self):
        """Whitespace around dates should be handled."""
        from gcg.cli import parse_date_range

        start, end = parse_date_range(" 2026-01-01 .. 2026-01-31 ")
        assert start == date(2026, 1, 1)
        assert end == date(2026, 1, 31)


class TestAmountRangeParsing:
    """Tests for amount range parsing."""

    def test_parse_amount_range_full(self):
        """Full amount range MIN..MAX should parse both values."""
        from gcg.cli import parse_amount_range

        min_amt, max_amt = parse_amount_range("10..100")
        assert min_amt == Decimal("10")
        assert max_amt == Decimal("100")

    def test_parse_amount_range_open_max(self):
        """Open-max range MIN.. should have None max."""
        from gcg.cli import parse_amount_range

        min_amt, max_amt = parse_amount_range("10..")
        assert min_amt == Decimal("10")
        assert max_amt is None

    def test_parse_amount_range_open_min(self):
        """Open-min range ..MAX should have None min."""
        from gcg.cli import parse_amount_range

        min_amt, max_amt = parse_amount_range("..100")
        assert min_amt is None
        assert max_amt == Decimal("100")

    def test_parse_amount_range_decimals(self):
        """Decimal amounts should parse correctly."""
        from gcg.cli import parse_amount_range

        min_amt, max_amt = parse_amount_range("10.50..99.99")
        assert min_amt == Decimal("10.50")
        assert max_amt == Decimal("99.99")

    def test_parse_amount_range_no_dots(self):
        """Range without .. should raise error."""
        from gcg.cli import parse_amount_range

        with pytest.raises(argparse.ArgumentTypeError):
            parse_amount_range("100")

    def test_parse_amount_range_invalid_number(self):
        """Invalid number should raise error."""
        from gcg.cli import parse_amount_range

        with pytest.raises(argparse.ArgumentTypeError):
            parse_amount_range("abc..100")


class TestResolveDateFilters:
    """Tests for combining date filter arguments."""

    def test_resolve_after_only(self):
        """--after alone should set start date."""
        from gcg.cli import resolve_date_filters

        class Args:
            after = date(2026, 1, 1)
            before = None
            date = None

        after, before = resolve_date_filters(Args())
        assert after == date(2026, 1, 1)
        assert before is None

    def test_resolve_before_only(self):
        """--before alone should set end date."""
        from gcg.cli import resolve_date_filters

        class Args:
            after = None
            before = date(2026, 2, 1)
            date = None

        after, before = resolve_date_filters(Args())
        assert after is None
        assert before == date(2026, 2, 1)

    def test_resolve_date_range(self):
        """--date range should set both with +1 day adjustment."""
        from gcg.cli import resolve_date_filters

        class Args:
            after = None
            before = None
            date = (date(2026, 1, 1), date(2026, 1, 31))

        after, before = resolve_date_filters(Args())
        assert after == date(2026, 1, 1)
        # End should be +1 day because --date is inclusive
        assert before == date(2026, 2, 1)

    def test_resolve_date_range_open_end(self):
        """--date A.. should only set start."""
        from gcg.cli import resolve_date_filters

        class Args:
            after = None
            before = None
            date = (date(2026, 1, 1), None)

        after, before = resolve_date_filters(Args())
        assert after == date(2026, 1, 1)
        assert before is None


class TestParserCreation:
    """Tests for the argument parser."""

    def test_parser_creates(self):
        """Parser should create without errors."""
        from gcg.cli import create_parser

        parser = create_parser()
        assert parser is not None

    def test_parser_accounts_command(self):
        """accounts command should parse correctly."""
        from gcg.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["accounts", "Bank"])
        assert args.command == "accounts"
        assert args.pattern == "Bank"

    def test_parser_accounts_with_options(self):
        """accounts with options should parse correctly."""
        from gcg.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(
            ["accounts", "^Expenses:", "--regex", "--show-guids"]
        )
        assert args.command == "accounts"
        assert args.pattern == "^Expenses:"
        assert args.regex is True
        assert args.show_guids is True

    def test_parser_grep_command(self):
        """grep command should parse correctly."""
        from gcg.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["grep", "amazon"])
        assert args.command == "grep"
        assert args.text == "amazon"

    def test_parser_grep_with_filters(self):
        """grep with date and amount filters should parse."""
        from gcg.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(
            [
                "grep",
                "amazon",
                "--after",
                "2026-01-01",
                "--amount",
                "10..100",
                "--signed",
            ]
        )
        assert args.command == "grep"
        assert args.text == "amazon"
        assert args.after == date(2026, 1, 1)
        assert args.amount == (Decimal("10"), Decimal("100"))
        assert args.signed is True

    def test_parser_ledger_command(self):
        """ledger command should parse correctly."""
        from gcg.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["ledger", "Assets:Bank"])
        assert args.command == "ledger"
        assert args.account_pattern == "Assets:Bank"

    def test_parser_tx_command(self):
        """tx command should parse correctly."""
        from gcg.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["tx", "abc123-guid"])
        assert args.command == "tx"
        assert args.guid == "abc123-guid"

    def test_parser_global_options(self):
        """Global options should parse correctly."""
        from gcg.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(
            [
                "--format",
                "json",
                "--no-header",
                "--sort",
                "amount",
                "--reverse",
                "--limit",
                "10",
                "accounts",
                "Bank",
            ]
        )
        assert args.format == "json"
        assert args.no_header is True
        assert args.sort == "amount"
        assert args.reverse is True
        assert args.limit == 10

    def test_parser_interactive_flag(self):
        """Interactive flag should parse."""
        from gcg.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["-i"])
        assert args.interactive is True

    def test_parser_cache_command(self):
        """cache command should parse correctly."""
        from gcg.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["cache", "build", "--force"])
        assert args.command == "cache"
        assert args.action == "build"
        assert args.force is True
