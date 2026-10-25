class ResourceNotFoundError(ValueError):
    """A requested resource does not exist."""


class BookingConflictError(ValueError):
    """The requested booking operation is not allowed."""


class PaymentConflictError(ValueError):
    """The requested payment operation conflicts with the current state."""