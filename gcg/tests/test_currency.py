"""Tests for currency conversion."""

from decimal import Decimal

from gcg.currency import (
    ConversionResult,
    determine_display_currency,
    get_account_currencies,
)


class TestConversionResult:
    """Tests for ConversionResult data class."""

    def test_conversion_result_no_conversion(self):
        """Same currency should not mark as converted."""
        result = ConversionResult(
            amount=Decimal("100"),
            currency="EUR",
            original_amount=Decimal("100"),
            original_currency="EUR",
            fx_rate=Decimal("1"),
            converted=False,
        )
        assert not result.converted
        assert result.fx_rate == Decimal("1")

    def test_conversion_result_with_conversion(self):
        """Different currency should mark as converted."""
        result = ConversionResult(
            amount=Decimal("85"),
            currency="EUR",
            original_amount=Decimal("100"),
            original_currency="GBP",
            fx_rate=Decimal("0.85"),
            converted=True,
        )
        assert result.converted
        assert result.amount == Decimal("85")
        assert result.original_amount == Decimal("100")


class TestDetermineDisplayCurrency:
    """Tests for display currency determination."""

    def test_split_mode_returns_none(self):
        """Split mode should return None (use per-row)."""
        result = determine_display_currency(
            mode="split",
            splits=[],
            account_filter_currencies={"EUR"},
            base_currency="EUR",
        )
        assert result is None

    def test_base_mode_returns_base(self):
        """Base mode should return base currency."""
        result = determine_display_currency(
            mode="base",
            splits=[],
            account_filter_currencies=None,
            base_currency="USD",
        )
        assert result == "USD"

    def test_account_mode_single_currency(self):
        """Account mode with single currency should use it."""
        result = determine_display_currency(
            mode="account",
            splits=[],
            account_filter_currencies={"GBP"},
            base_currency="EUR",
        )
        assert result == "GBP"

    def test_account_mode_multiple_currencies(self):
        """Account mode with multiple currencies should return None."""
        result = determine_display_currency(
            mode="account",
            splits=[],
            account_filter_currencies={"GBP", "USD"},
            base_currency="EUR",
        )
        assert result is None

    def test_auto_mode_account_single_currency(self):
        """Auto mode should use account currency if single."""
        result = determine_display_currency(
            mode="auto",
            splits=[],
            account_filter_currencies={"GBP"},
            base_currency="EUR",
        )
        assert result == "GBP"

    def test_auto_mode_fallback_to_base(self):
        """Auto mode should fall back to base currency."""
        result = determine_display_currency(
            mode="auto",
            splits=[],
            account_filter_currencies={"GBP", "USD", "EUR"},
            base_currency="EUR",
        )
        assert result == "EUR"


class TestGetAccountCurrencies:
    """Tests for getting currencies from accounts."""

    def test_empty_accounts(self):
        """Empty account list should return empty set."""
        result = get_account_currencies([])
        assert result == set()

    def test_accounts_with_commodities(self):
        """Should extract commodities from accounts."""

        class MockCommodity:
            def __init__(self, mnemonic):
                self.mnemonic = mnemonic

        class MockAccount:
            def __init__(self, commodity):
                self.commodity = commodity

        accounts = [
            MockAccount(MockCommodity("EUR")),
            MockAccount(MockCommodity("GBP")),
            MockAccount(MockCommodity("EUR")),  # Duplicate
        ]

        result = get_account_currencies(accounts)
        assert result == {"EUR", "GBP"}

    def test_accounts_without_commodity(self):
        """Accounts without commodity should be skipped."""

        class MockAccount:
            commodity = None

        accounts = [MockAccount(), MockAccount()]
        result = get_account_currencies(accounts)
        assert result == set()
