"""Domain errors. Raised by pure code only; adapters map them to transport errors."""


class DomainError(Exception):
    """Base class for every deterministic domain refusal."""


class MoneyError(DomainError):
    """Invalid money value or cross-currency arithmetic."""


class StaleApprovalError(DomainError):
    """Approval evidence no longer matches current treasury evidence."""


class ReserveFloorError(DomainError):
    """Execution would breach the reserve floor for a currency."""


class DuplicateRequestIdError(DomainError):
    """A request_id was reused for a different payload inside the lock window."""


class CapabilityError(DomainError):
    """Actor does not hold the capability required for the attempted action."""


class ReceiptError(DomainError):
    """Receipt construction or proof verification failed."""
