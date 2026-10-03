class InterventionActivationError(ValueError):
    """A prescription item cannot be activated as an intervention."""


class InterventionNotFoundError(LookupError):
    """Intervention does not exist."""
