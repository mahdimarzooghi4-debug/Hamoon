class ReferralCreationError(ValueError):
    """Referral cannot be created from the current matching decision."""


class ReferralTransitionError(ValueError):
    """Referral state transition is invalid."""


class ReferralVersionConflictError(ValueError):
    """Referral changed since the caller loaded it."""


class ReferralIdempotencyConflictError(ValueError):
    """Idempotency key/event was reused with different semantics."""


class ReferralProviderScopeError(LookupError):
    """Provider cannot access the requested referral."""
