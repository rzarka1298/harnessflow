"""Existing behavior must keep working when reports are added."""

import tempfile
import unittest
from pathlib import Path

from expenses import add_expense, load_expenses


class ExpenseTests(unittest.TestCase):
    def test_add_persists_money_and_date(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "expenses.json"
            add_expense(ledger, "2026-01-04", "Food", "2.30")
            self.assertEqual(
                load_expenses(ledger),
                [{"date": "2026-01-04", "category": "Food", "amount": "2.30"}],
            )

    def test_invalid_money_does_not_change_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "expenses.json"
            with self.assertRaises(ValueError):
                add_expense(ledger, "2026-01-04", "Food", "-1")
            self.assertFalse(ledger.exists())


if __name__ == "__main__":
    unittest.main()
