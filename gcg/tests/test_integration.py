"""Integration tests for gcg using a test GnuCash book."""

import io
from contextlib import redirect_stdout

import pytest

# Skip all tests if piecash is not available
pytest.importorskip("piecash")


class TestBookOpening:
    """Tests for opening and reading the book."""

    def test_open_book(self, test_book_path):
        """Book should open successfully."""
        from gcg.book import open_gnucash_book

        with open_gnucash_book(test_book_path) as (book, info):
            assert book is not None
            assert info.default_currency == "EUR"
            assert info.account_count > 0
            assert info.transaction_count > 0

    def test_book_info_counts(self, test_book_path):
        """Book info should have correct counts."""
        from gcg.book import open_gnucash_book

        with open_gnucash_book(test_book_path) as (book, info):
            # We created specific accounts and transactions
            assert info.account_count >= 9  # At least our created accounts
            assert info.transaction_count == 6


class TestAccountSearch:
    """Tests for account search functionality."""

    def test_find_account_by_substring(self, test_book_path):
        """Should find accounts by substring."""
        from gcg.book import get_account_by_pattern, open_gnucash_book

        with open_gnucash_book(test_book_path) as (book, info):
            accounts = get_account_by_pattern(book, "Bank")
            names = [a.fullname for a in accounts]
            assert any("Bank" in n for n in names)

    def test_find_account_case_insensitive(self, test_book_path):
        """Search should be case-insensitive by default."""
        from gcg.book import get_account_by_pattern, open_gnucash_book

        with open_gnucash_book(test_book_path) as (book, info):
            accounts1 = get_account_by_pattern(book, "bank")
            accounts2 = get_account_by_pattern(book, "BANK")
            assert len(accounts1) == len(accounts2)

    def test_find_account_with_subtree(self, test_book_path):
        """Should include subtree accounts by default."""
        from gcg.book import get_account_by_pattern, open_gnucash_book

        with open_gnucash_book(test_book_path) as (book, info):
            # Searching for "Food" should include Groceries and Restaurants
            accounts = get_account_by_pattern(book, "Food")
            names = [a.fullname for a in accounts]
            assert any("Food" in n for n in names)
            assert any("Groceries" in n for n in names)
            assert any("Restaurants" in n for n in names)

    def test_find_account_without_subtree(self, test_book_path):
        """Should exclude subtree when requested."""
        from gcg.book import get_account_by_pattern, open_gnucash_book

        with open_gnucash_book(test_book_path) as (book, info):
            # Use regex to match exactly "Assets:Bank" (ending in Bank)
            # With subtree should include descendants (Checking, Savings)
            accounts_with = get_account_by_pattern(
                book, "Assets:Bank$", is_regex=True, include_subtree=True
            )
            accounts_without = get_account_by_pattern(
                book, "Assets:Bank$", is_regex=True, include_subtree=False
            )

            # With subtree should include Checking and Savings
            names_with = [a.fullname for a in accounts_with]
            assert any("Checking" in n for n in names_with)
            assert any("Savings" in n for n in names_with)

            # Without subtree should only have Bank itself
            names_without = [a.fullname for a in accounts_without]
            assert len(names_without) == 1
            assert names_without[0].endswith("Bank")

    def test_find_account_regex(self, test_book_path):
        """Should support regex patterns."""
        from gcg.book import get_account_by_pattern, open_gnucash_book

        with open_gnucash_book(test_book_path) as (book, info):
            # Match accounts containing "Checking" or "Savings"
            accounts = get_account_by_pattern(
                book,
                "(Checking|Savings)",
                is_regex=True,
                include_subtree=False,
            )
            names = [a.fullname for a in accounts]
            assert any("Checking" in n for n in names)
            assert any("Savings" in n for n in names)

    def test_invalid_regex_raises(self, test_book_path):
        """Invalid regex should raise InvalidPatternError."""
        from gcg.book import (
            InvalidPatternError,
            get_account_by_pattern,
            open_gnucash_book,
        )

        with open_gnucash_book(test_book_path) as (book, info):
            with pytest.raises(InvalidPatternError):
                get_account_by_pattern(book, "[invalid", is_regex=True)


class TestGrepCommand:
    """Tests for grep search functionality."""

    def test_grep_finds_transaction(self, config_with_test_book):
        """grep should find transactions by description."""
        from gcg.cli import cmd_grep, create_parser

        parser = create_parser()
        args = parser.parse_args(["grep", "Tesco"])
        result = cmd_grep(args, config_with_test_book)
        assert result == 0  # Found matches

    def test_grep_no_matches(self, config_with_test_book):
        """grep should return 1 when no matches found."""
        from gcg.cli import cmd_grep, create_parser

        parser = create_parser()
        args = parser.parse_args(["grep", "nonexistent12345"])
        result = cmd_grep(args, config_with_test_book)
        assert result == 1  # No matches

    def test_grep_with_date_filter(self, config_with_test_book):
        """grep should filter by date."""
        from gcg.cli import cmd_grep, create_parser

        parser = create_parser()
        # Only January 15 onwards
        args = parser.parse_args(
            ["grep", ".", "--regex", "--after", "2026-01-15"]
        )
        result = cmd_grep(args, config_with_test_book)
        assert result == 0

    def test_grep_with_amount_filter(self, config_with_test_book):
        """grep should filter by amount."""
        from gcg.cli import cmd_grep, create_parser

        parser = create_parser()
        # Amounts between 80 and 130
        args = parser.parse_args(
            ["grep", ".", "--regex", "--amount", "80..130"]
        )
        result = cmd_grep(args, config_with_test_book)
        assert result == 0

    def test_grep_case_insensitive(self, config_with_test_book):
        """grep should be case-insensitive by default."""
        from gcg.cli import cmd_grep, create_parser

        parser = create_parser()
        args = parser.parse_args(["grep", "TESCO"])
        result = cmd_grep(args, config_with_test_book)
        assert result == 0  # Should still find "Tesco"


class TestLedgerCommand:
    """Tests for ledger command."""

    def test_ledger_account(self, config_with_test_book):
        """ledger should display splits for an account."""
        from gcg.cli import cmd_ledger, create_parser

        parser = create_parser()
        args = parser.parse_args(["ledger", "Checking"])
        result = cmd_ledger(args, config_with_test_book)
        assert result == 0

    def test_ledger_no_match(self, config_with_test_book):
        """ledger should return 1 for non-existent account."""
        from gcg.cli import cmd_ledger, create_parser

        parser = create_parser()
        args = parser.parse_args(["ledger", "NonexistentAccount123"])
        result = cmd_ledger(args, config_with_test_book)
        assert result == 1

    def test_ledger_with_date_range(self, config_with_test_book):
        """ledger should respect date filters."""
        from gcg.cli import cmd_ledger, create_parser

        parser = create_parser()
        args = parser.parse_args(
            ["ledger", "Checking", "--date", "2026-01-01..2026-01-31"]
        )
        result = cmd_ledger(args, config_with_test_book)
        assert result == 0


class TestDoctorCommand:
    """Tests for doctor command."""

    def test_doctor_runs(self, config_with_test_book):
        """doctor command should run successfully."""
        from gcg.cli import cmd_doctor, create_parser

        parser = create_parser()
        args = parser.parse_args(["doctor"])
        result = cmd_doctor(args, config_with_test_book)
        assert result == 0


class TestCacheCommand:
    """Tests for cache command."""

    def test_cache_status_no_cache(self, config_with_test_book):
        """cache status should work when no cache exists."""
        from gcg.cli import cmd_cache, create_parser

        parser = create_parser()
        args = parser.parse_args(["cache", "status"])
        result = cmd_cache(args, config_with_test_book)
        assert result == 0

    def test_cache_build_and_drop(self, config_with_test_book, tmp_path):
        """cache build and drop should work."""
        from gcg.cli import cmd_cache, create_parser
        from gcg.config import Config

        # Use a temp path for the cache
        config = Config(
            book_path=config_with_test_book.book_path,
            cache_path=tmp_path / "test_cache.sqlite",
        )

        parser = create_parser()

        # Build
        args = parser.parse_args(["cache", "build"])
        result = cmd_cache(args, config)
        assert result == 0
        assert (tmp_path / "test_cache.sqlite").exists()

        # Drop
        args = parser.parse_args(["cache", "drop"])
        result = cmd_cache(args, config)
        assert result == 0
        assert not (tmp_path / "test_cache.sqlite").exists()


class TestNotesLookup:
    """Tests for notes batch lookup."""

    def test_batch_notes_empty_list(self, test_book_path):
        """Should handle empty guid list."""
        from gcg.book import get_transaction_notes_batch

        result = get_transaction_notes_batch(test_book_path, [], False)
        assert result == {}

    def test_batch_notes_nonexistent_guids(self, test_book_path):
        """Should return empty dict for non-existent guids."""
        from gcg.book import get_transaction_notes_batch

        result = get_transaction_notes_batch(
            test_book_path,
            ["nonexistent-guid-1", "nonexistent-guid-2"],
            False,
        )
        assert result == {}


class TestOutputFormats:
    """Tests for different output formats."""

    def test_json_output(self, config_with_test_book):
        """Should produce valid JSON output."""
        import json

        from gcg.cli import cmd_grep, create_parser

        parser = create_parser()
        args = parser.parse_args(["--format", "json", "grep", "Tesco"])

        # Capture stdout
        captured = io.StringIO()
        with redirect_stdout(captured):
            result = cmd_grep(args, config_with_test_book)

        assert result == 0
        output = captured.getvalue()
        # Should be valid JSON
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_csv_output(self, config_with_test_book):
        """Should produce valid CSV output."""
        from gcg.cli import cmd_grep, create_parser

        parser = create_parser()
        args = parser.parse_args(["--format", "csv", "grep", "Tesco"])

        captured = io.StringIO()
        with redirect_stdout(captured):
            result = cmd_grep(args, config_with_test_book)

        assert result == 0
        output = captured.getvalue()
        lines = output.strip().split("\n")
        # Should have header + at least one data row
        assert len(lines) >= 2
        # Header should have columns
        assert "," in lines[0]
