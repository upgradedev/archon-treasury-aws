"""Money in integer minor units (cents). No fractional arithmetic anywhere.

Trap T2 (TRAPS.md): the Airwallex REST boundary takes major units, where
100 means 100.00. This module never crosses that boundary. It only renders
a major-unit string via to_major_str() for display and for the single
adapter that is allowed to convert.
"""

from dataclasses import dataclass

from kerdon.errors import MoneyError

SUPPORTED_CURRENCIES = ("USD", "EUR", "GBP", "USDZ")


@dataclass(frozen=True, slots=True)
class Money:
    amount_cents: int
    currency: str

    def __post_init__(self) -> None:
        # bool is a subclass of int in Python. Reject it explicitly.
        if isinstance(self.amount_cents, bool) or not isinstance(self.amount_cents, int):
            raise MoneyError(
                f"amount_cents must be int cents, got {type(self.amount_cents).__name__}"
            )
        if self.currency not in SUPPORTED_CURRENCIES:
            raise MoneyError(
                f"unsupported currency {self.currency!r}; expected one of {SUPPORTED_CURRENCIES}"
            )

    def _same_currency(self, other: "Money") -> None:
        if not isinstance(other, Money):
            raise MoneyError("money arithmetic requires another Money value")
        if self.currency != other.currency:
            raise MoneyError(
                f"cross-currency arithmetic refused: {self.currency} vs {other.currency}"
            )

    def __add__(self, other: "Money") -> "Money":
        self._same_currency(other)
        return Money(self.amount_cents + other.amount_cents, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._same_currency(other)
        return Money(self.amount_cents - other.amount_cents, self.currency)

    def __neg__(self) -> "Money":
        return Money(-self.amount_cents, self.currency)

    def __lt__(self, other: "Money") -> bool:
        self._same_currency(other)
        return self.amount_cents < other.amount_cents

    def __le__(self, other: "Money") -> bool:
        self._same_currency(other)
        return self.amount_cents <= other.amount_cents

    def __gt__(self, other: "Money") -> bool:
        self._same_currency(other)
        return self.amount_cents > other.amount_cents

    def __ge__(self, other: "Money") -> bool:
        self._same_currency(other)
        return self.amount_cents >= other.amount_cents

    @property
    def is_zero(self) -> bool:
        return self.amount_cents == 0

    @property
    def is_positive(self) -> bool:
        return self.amount_cents > 0

    def to_major_str(self) -> str:
        """Render major units with exactly two decimals, integer math only.

        Examples: 5000 USD cents -> "50.00"; -123 EUR cents -> "-1.23".
        This string is the only shape an adapter may send to an API that
        takes major units (Trap T2).
        """
        sign = "-" if self.amount_cents < 0 else ""
        whole, frac = divmod(abs(self.amount_cents), 100)
        return f"{sign}{whole}.{frac:02d}"

    def spoken(self) -> str:
        """Short plain-language amount for spoken and screen-reader receipts."""
        return f"{self.currency} {self.to_major_str()} ({self.amount_cents} cents)"


def zero(currency: str) -> Money:
    return Money(0, currency)
