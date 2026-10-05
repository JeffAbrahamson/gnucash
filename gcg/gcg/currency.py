"""
Multi-currency display and conversion for gcg.

Handles currency conversion using the GnuCash price database,
with configurable display modes and lookback windows.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional


@dataclass
class ConversionResult:
    """Result of a currency conversion attempt."""

    amount: Decimal
    currency: str
    original_amount: Decimal
    original_currency: str
    fx_rate: Optional[Decimal]  # None if no conversion was performed
    converted: bool  # True if conversion was successful


class CurrencyConverter:
    """
    Handles currency conversion using GnuCash price database.

    Supports multiple display modes:
    - auto: Automatic currency selection based on context
    - base: Always display in base currency when possible
    - split: Always display original split currency
    - account: Display in account's commodity
    """

    def __init__(
        self,
        db_path: Path,
        base_currency: str = "EUR",
        lookback_days: int = 30,
    ):
        """
        Initialize converter.

        Args:
            db_path: Path to GnuCash SQLite file
            base_currency: Default target currency for conversions
            lookback_days: Max days to look back for price quotes
        """
        self.db_path = db_path
        self.base_currency = base_currency
        self.lookback_days = lookback_days
        self._price_cache: dict[tuple[str, str, date], Optional[Decimal]] = {}

    def get_price(
        self,
        from_currency: str,
        to_currency: str,
        on_date: date,
    ) -> Optional[Decimal]:
        """
        Get exchange rate from the price database.

        Looks for prices on or before the given date within the
        lookback window.

        Args:
            from_currency: Source currency mnemonic
            to_currency: Target currency mnemonic
            on_date: Date to find price for

        Returns:
            Exchange rate as Decimal, or None if not found
        """
        if from_currency == to_currency:
            return Decimal("1")

        # Check cache
        cache_key = (from_currency, to_currency, on_date)
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]

        # Also check reverse direction in cache
        reverse_key = (to_currency, from_currency, on_date)
        if reverse_key in self._price_cache:
            reverse_rate = self._price_cache[reverse_key]
            if reverse_rate is not None:
                rate = Decimal("1") / reverse_rate
                self._price_cache[cache_key] = rate
                return rate

        # Query database
        rate = self._lookup_price(from_currency, to_currency, on_date)
        self._price_cache[cache_key] = rate
        return rate

    def _lookup_price(
        self,
        from_currency: str,
        to_currency: str,
        on_date: date,
    ) -> Optional[Decimal]:
        """
        Look up price in the database.

        Tries both direct and inverse lookups.
        """
        uri = f"file:{self.db_path}?mode=ro"
        earliest_date = on_date - timedelta(days=self.lookback_days)

        try:
            conn = sqlite3.connect(uri, uri=True)
            cursor = conn.cursor()

            # Try direct lookup: from_currency -> to_currency
            # GnuCash stores prices as commodity -> currency
            cursor.execute(
                """
                SELECT value_num, value_denom
                FROM prices p
                JOIN commodities c1 ON p.commodity_guid = c1.guid
                JOIN commodities c2 ON p.currency_guid = c2.guid
                WHERE c1.mnemonic = ?
                  AND c2.mnemonic = ?
                  AND date(p.date) <= ?
                  AND date(p.date) >= ?
                ORDER BY p.date DESC
                LIMIT 1
                """,
                (
                    from_currency,
                    to_currency,
                    on_date.isoformat(),
                    earliest_date.isoformat(),
                ),
            )
            result = cursor.fetchone()

            if result:
                num, denom = result
                rate = Decimal(num) / Decimal(denom)
                conn.close()
                return rate

            # Try inverse lookup: to_currency -> from_currency
            cursor.execute(
                """
                SELECT value_num, value_denom
                FROM prices p
                JOIN commodities c1 ON p.commodity_guid = c1.guid
                JOIN commodities c2 ON p.currency_guid = c2.guid
                WHERE c1.mnemonic = ?
                  AND c2.mnemonic = ?
                  AND date(p.date) <= ?
                  AND date(p.date) >= ?
                ORDER BY p.date DESC
                LIMIT 1
                """,
                (
                    to_currency,
                    from_currency,
                    on_date.isoformat(),
                    earliest_date.isoformat(),
                ),
            )
            result = cursor.fetchone()

            conn.close()

            if result:
                num, denom = result
                inverse_rate = Decimal(num) / Decimal(denom)
                return Decimal("1") / inverse_rate

            return None

        except sqlite3.Error:
            return None

    def convert(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        on_date: date,
    ) -> ConversionResult:
        """
        Convert an amount between currencies.

        Args:
            amount: Amount to convert
            from_currency: Source currency
            to_currency: Target currency
            on_date: Date for exchange rate lookup

        Returns:
            ConversionResult with converted amount and metadata
        """
        if from_currency == to_currency:
            return ConversionResult(
                amount=amount,
                currency=to_currency,
                original_amount=amount,
                original_currency=from_currency,
                fx_rate=Decimal("1"),
                converted=False,
            )

        rate = self.get_price(from_currency, to_currency, on_date)

        if rate is None:
            # Conversion failed, return original
            return ConversionResult(
                amount=amount,
                currency=from_currency,
                original_amount=amount,
                original_currency=from_currency,
                fx_rate=None,
                converted=False,
            )

        converted_amount = amount * rate
        return ConversionResult(
            amount=converted_amount,
            currency=to_currency,
            original_amount=amount,
            original_currency=from_currency,
            fx_rate=rate,
            converted=True,
        )


def determine_display_currency(
    mode: str,
    splits: list,
    account_filter_currencies: Optional[set[str]],
    base_currency: str,
) -> Optional[str]:
    """
    Determine which currency to display based on mode and context.

    Args:
        mode: Currency display mode (auto, base, split, account)
        splits: List of splits to display
        account_filter_currencies: Set of currencies from filtered accounts
        base_currency: Configured base currency

    Returns:
        Target currency for display, or None to use per-row currency
    """
    if mode == "split":
        return None  # Use each split's original currency

    if mode == "base":
        return base_currency

    if mode == "account":
        # If account filter specified a single currency, use it
        if account_filter_currencies and len(account_filter_currencies) == 1:
            return next(iter(account_filter_currencies))
        return None  # Fall back to per-row

    # mode == "auto"
    # Step 1: Check if account filter specifies single currency
    if account_filter_currencies and len(account_filter_currencies) == 1:
        return next(iter(account_filter_currencies))

    # Step 2: Check if all splits share single currency
    currencies = set()
    for split in splits:
        if hasattr(split, "account") and hasattr(split.account, "commodity"):
            if split.account.commodity:
                currencies.add(split.account.commodity.mnemonic)

    if len(currencies) == 1:
        return next(iter(currencies))

    # Step 3: Fall back to base currency
    return base_currency


def get_account_currencies(accounts: list) -> set[str]:
    """Get the set of currencies from a list of accounts."""
    currencies = set()
    for account in accounts:
        if hasattr(account, "commodity") and account.commodity:
            currencies.add(account.commodity.mnemonic)
    return currencies
