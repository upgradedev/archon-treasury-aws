"""Run: set PYTHONPATH=src && python -m unittest discover -s tests -v"""

import unittest

from kerdon.errors import MoneyError
from kerdon.money import Money


class MoneyTest(unittest.TestCase):
    def test_integer_cents_only(self):
        self.assertEqual(Money(5000, "USD").amount_cents, 5000)
        with self.assertRaises(MoneyError):
            Money(True, "USD")  # bool is an int subclass; must be refused
        with self.assertRaises(MoneyError):
            Money(50.0, "USD")
        with self.assertRaises(MoneyError):
            Money("5000", "USD")

    def test_currency_allowlist(self):
        for cur in ("USD", "EUR", "GBP", "USDZ"):
            self.assertEqual(Money(1, cur).currency, cur)
        with self.assertRaises(MoneyError):
            Money(1, "JPY")

    def test_same_currency_arithmetic(self):
        self.assertEqual(Money(100, "EUR") + Money(250, "EUR"), Money(350, "EUR"))
        self.assertEqual(Money(100, "EUR") - Money(250, "EUR"), Money(-150, "EUR"))
        self.assertTrue(Money(99, "GBP") < Money(100, "GBP"))

    def test_cross_currency_refused(self):
        with self.assertRaises(MoneyError):
            _ = Money(100, "USD") + Money(100, "EUR")
        with self.assertRaises(MoneyError):
            _ = Money(100, "USD") < Money(100, "EUR")

    def test_major_str_trap_t2_rendering(self):
        # Trap T2: 5000 cents is 50.00 major units at the Airwallex boundary.
        self.assertEqual(Money(5000, "USD").to_major_str(), "50.00")
        self.assertEqual(Money(5, "USD").to_major_str(), "0.05")
        self.assertEqual(Money(-123, "EUR").to_major_str(), "-1.23")
        self.assertEqual(Money(0, "GBP").to_major_str(), "0.00")
        self.assertEqual(Money(100, "USD").to_major_str(), "1.00")

    def test_spoken_amount(self):
        self.assertEqual(Money(5000, "USD").spoken(), "USD 50.00 (5000 cents)")


if __name__ == "__main__":
    unittest.main()
