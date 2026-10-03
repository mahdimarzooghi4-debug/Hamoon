class ProviderResultError(ValueError):
    """Provider result submission or lookup is invalid."""


class ProviderResultIdempotencyConflictError(ValueError):
    """External result id was reused with a different payload."""


class ProviderResultScopeError(LookupError):
    """Provider cannot access the requested referral/result."""
