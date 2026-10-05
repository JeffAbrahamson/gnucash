"""Tests for output formatting."""

import io
import json
from datetime import date
from decimal import Decimal

import pytest

from gcg.output import (
    AccountRow,
    OutputFormatter,
    SplitRow,
    _truncate,
    _format_amount,
)


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_truncate_short_string(self):
        """Short strings should not be truncated."""
        result = _truncate("hello", 10)
        assert result == "hello"

    def test_truncate_exact_length(self):
        """Strings at exact length should not be truncated."""
        result = _truncate("hello", 5)
        assert result == "hello"

    def test_truncate_long_string(self):
        """Long strings should be truncated with ellipsis."""
        result = _truncate("hello world", 8)
        assert result == "hello..."
        assert len(result) == 8

    def test_format_amount_positive(self):
        """Positive amounts should format correctly."""
        result = _format_amount(Decimal("1234.56"))
        assert result == "1,234.56"

    def test_format_amount_negative(self):
        """Negative amounts should format correctly."""
        result = _format_amount(Decimal("-1234.56"))
        assert result == "-1,234.56"

    def test_format_amount_none(self):
        """None should return empty string."""
        result = _format_amount(None)
        assert result == ""


class TestSplitRow:
    """Tests for SplitRow data class."""

    def test_split_row_to_dict(self):
        """SplitRow should convert to dict correctly."""
        row = SplitRow(
            date=date(2026, 1, 15),
            description="Test transaction",
            account="Assets:Bank",
            memo="Test memo",
            notes="Test notes",
            amount=Decimal("100.00"),
            currency="EUR",
            fx_rate=None,
            tx_guid="tx-123",
            split_guid="split-456",
        )
        result = row.to_dict()

        assert result["date"] == "2026-01-15"
        assert result["description"] == "Test transaction"
        assert result["account"] == "Assets:Bank"
        assert result["memo"] == "Test memo"
        assert result["notes"] == "Test notes"
        assert result["amount"] == "100.00"
        assert result["currency"] == "EUR"
        assert result["fx_rate"] is None
        assert result["tx_guid"] == "tx-123"
        assert result["split_guid"] == "split-456"

    def test_split_row_to_dict_with_conversion(self):
        """SplitRow with conversion should include fx_rate."""
        row = SplitRow(
            date=date(2026, 1, 15),
            description="Test",
            account="Assets:Bank",
            memo=None,
            notes=None,
            amount=Decimal("85.00"),
            currency="EUR",
            fx_rate=Decimal("0.85"),
            tx_guid="tx-123",
            split_guid="split-456",
            amount_orig=Decimal("100.00"),
            currency_orig="GBP",
        )
        result = row.to_dict()

        assert result["amount"] == "85.00"
        assert result["currency"] == "EUR"
        assert result["fx_rate"] == "0.85"
        assert result["amount_orig"] == "100.00"
        assert result["currency_orig"] == "GBP"


class TestAccountRow:
    """Tests for AccountRow data class."""

    def test_account_row_to_dict(self):
        """AccountRow should convert to dict correctly."""
        row = AccountRow(
            name="Assets:Bank:UK",
            type="BANK",
            currency="GBP",
            guid="acc-123",
        )
        result = row.to_dict(show_guid=True)

        assert result["name"] == "Assets:Bank:UK"
        assert result["type"] == "BANK"
        assert result["currency"] == "GBP"
        assert result["guid"] == "acc-123"

    def test_account_row_to_dict_no_guid(self):
        """AccountRow without show_guid should omit guid."""
        row = AccountRow(
            name="Assets:Bank",
            type="BANK",
            currency="EUR",
            guid="acc-123",
        )
        result = row.to_dict(show_guid=False)

        assert "guid" not in result


class TestOutputFormatter:
    """Tests for OutputFormatter class."""

    @pytest.fixture
    def sample_splits(self):
        """Create sample split rows for testing."""
        return [
            SplitRow(
                date=date(2026, 1, 15),
                description="Amazon Purchase",
                account="Expenses:Shopping",
                memo="Order #123",
                notes=None,
                amount=Decimal("50.00"),
                currency="EUR",
                fx_rate=None,
                tx_guid="tx-1",
                split_guid="split-1",
            ),
            SplitRow(
                date=date(2026, 1, 16),
                description="Grocery Store",
                account="Expenses:Food",
                memo=None,
                notes=None,
                amount=Decimal("25.50"),
                currency="EUR",
                fx_rate=None,
                tx_guid="tx-2",
                split_guid="split-2",
            ),
        ]

    def test_format_splits_json(self, sample_splits):
        """JSON output should be valid JSON array."""
        formatter = OutputFormatter(format_type="json")
        output = io.StringIO()
        formatter.format_splits(sample_splits, file=output)

        result = json.loads(output.getvalue())
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["description"] == "Amazon Purchase"
        assert result[1]["amount"] == "25.50"

    def test_format_splits_csv(self, sample_splits):
        """CSV output should have header and rows."""
        formatter = OutputFormatter(format_type="csv")
        output = io.StringIO()
        formatter.format_splits(sample_splits, file=output)

        lines = output.getvalue().strip().split("\n")
        assert len(lines) == 3  # Header + 2 data rows
        assert "date" in lines[0]
        assert "description" in lines[0]

    def test_format_splits_csv_no_header(self, sample_splits):
        """CSV without header should only have data rows."""
        formatter = OutputFormatter(format_type="csv", show_header=False)
        output = io.StringIO()
        formatter.format_splits(sample_splits, file=output)

        lines = output.getvalue().strip().split("\n")
        assert len(lines) == 2  # No header, just data

    def test_format_empty_splits(self):
        """Empty split list should produce no output."""
        formatter = OutputFormatter(format_type="json")
        output = io.StringIO()
        formatter.format_splits([], file=output)
        assert output.getvalue() == ""

    @pytest.fixture
    def sample_accounts(self):
        """Create sample account rows for testing."""
        return [
            AccountRow(name="Assets:Bank", type="BANK", currency="EUR"),
            AccountRow(name="Assets:Cash", type="CASH", currency="EUR"),
        ]

    def test_format_accounts_json(self, sample_accounts):
        """Account JSON output should be valid."""
        formatter = OutputFormatter(format_type="json")
        output = io.StringIO()
        formatter.format_accounts(sample_accounts, file=output)

        result = json.loads(output.getvalue())
        assert len(result) == 2
        assert result[0]["name"] == "Assets:Bank"
