"""Pytest fixtures for gcg integration tests."""

import tempfile
import warnings
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

# Suppress SQLAlchemy warnings from piecash before importing it
# Must be done before any piecash import
warnings.filterwarnings("ignore", module="piecash.*")
warnings.filterwarnings("ignore", module="sqlalchemy.*")

try:
    from sqlalchemy.exc import SAWarning
    warnings.filterwarnings("ignore", category=SAWarning)
except ImportError:
    pass


# Skip all integration tests if piecash is not available
piecash = pytest.importorskip("piecash")


@pytest.fixture(scope="session")
def test_book_path():
    """
    Create a temporary GnuCash SQLite book for testing.

    This fixture creates a small test book with:
    - A few accounts (Assets, Expenses, Income)
    - Several transactions with various descriptions
    - Multiple currencies (EUR, GBP)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        book_path = Path(tmpdir) / "test_book.gnucash"

        # Create book
        book = piecash.create_book(
            sqlite_file=str(book_path),
            currency="EUR",
            overwrite=True,
        )

        # Create account hierarchy
        root = book.root_account

        # Assets
        assets = piecash.Account(
            name="Assets",
            type="ASSET",
            commodity=book.default_currency,
            parent=root,
        )
        bank = piecash.Account(
            name="Bank",
            type="BANK",
            commodity=book.default_currency,
            parent=assets,
        )
        checking = piecash.Account(
            name="Checking",
            type="BANK",
            commodity=book.default_currency,
            parent=bank,
        )
        savings = piecash.Account(
            name="Savings",
            type="BANK",
            commodity=book.default_currency,
            parent=bank,
        )

        # Expenses
        expenses = piecash.Account(
            name="Expenses",
            type="EXPENSE",
            commodity=book.default_currency,
            parent=root,
        )
        food = piecash.Account(
            name="Food",
            type="EXPENSE",
            commodity=book.default_currency,
            parent=expenses,
        )
        groceries = piecash.Account(
            name="Groceries",
            type="EXPENSE",
            commodity=book.default_currency,
            parent=food,
        )
        restaurants = piecash.Account(
            name="Restaurants",
            type="EXPENSE",
            commodity=book.default_currency,
            parent=food,
        )
        utilities = piecash.Account(
            name="Utilities",
            type="EXPENSE",
            commodity=book.default_currency,
            parent=expenses,
        )

        # Income
        income = piecash.Account(
            name="Income",
            type="INCOME",
            commodity=book.default_currency,
            parent=root,
        )
        salary = piecash.Account(
            name="Salary",
            type="INCOME",
            commodity=book.default_currency,
            parent=income,
        )

        # Create transactions (automatically added to book session)
        # Transaction 1: Grocery shopping at Tesco
        piecash.Transaction(
            currency=book.default_currency,
            description="Tesco groceries",
            post_date=date(2026, 1, 5),
            splits=[
                piecash.Split(account=groceries, value=Decimal("45.50")),
                piecash.Split(account=checking, value=Decimal("-45.50")),
            ],
        )

        # Transaction 2: Restaurant - Amazon Fresh delivery
        piecash.Transaction(
            currency=book.default_currency,
            description="Amazon Fresh delivery",
            post_date=date(2026, 1, 10),
            splits=[
                piecash.Split(
                    account=groceries,
                    value=Decimal("78.25"),
                    memo="Weekly groceries",
                ),
                piecash.Split(account=checking, value=Decimal("-78.25")),
            ],
        )

        # Transaction 3: Salary
        piecash.Transaction(
            currency=book.default_currency,
            description="Monthly salary",
            post_date=date(2026, 1, 15),
            splits=[
                piecash.Split(account=checking, value=Decimal("3500.00")),
                piecash.Split(account=salary, value=Decimal("-3500.00")),
            ],
        )

        # Transaction 4: Electric bill
        piecash.Transaction(
            currency=book.default_currency,
            description="EDF electricity bill",
            post_date=date(2026, 1, 20),
            splits=[
                piecash.Split(account=utilities, value=Decimal("125.00")),
                piecash.Split(account=checking, value=Decimal("-125.00")),
            ],
        )

        # Transaction 5: Restaurant dinner
        piecash.Transaction(
            currency=book.default_currency,
            description="Dinner at Le Petit Bistro",
            post_date=date(2026, 1, 25),
            splits=[
                piecash.Split(
                    account=restaurants,
                    value=Decimal("89.50"),
                    memo="Birthday dinner",
                ),
                piecash.Split(account=checking, value=Decimal("-89.50")),
            ],
        )

        # Transaction 6: Transfer to savings
        piecash.Transaction(
            currency=book.default_currency,
            description="Monthly savings transfer",
            post_date=date(2026, 1, 28),
            splits=[
                piecash.Split(account=savings, value=Decimal("500.00")),
                piecash.Split(account=checking, value=Decimal("-500.00")),
            ],
        )

        book.save()
        book.close()

        yield book_path


@pytest.fixture
def config_with_test_book(test_book_path):
    """Create a Config object pointing to the test book."""
    from gcg.config import Config

    return Config(book_path=test_book_path)
