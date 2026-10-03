class DataSourceNotFoundError(LookupError):
    """Requested data source does not exist or is inactive."""


class HouseholdFactNotFoundError(LookupError):
    """Requested household fact does not exist in the household."""


class InvalidFactValueError(ValueError):
    """Fact value does not match its declared value type."""


class InvalidValidationTransitionError(ValueError):
    """Requested fact-validation transition is not allowed."""


class FactNotValidatedError(ValueError):
    """Only a validated fact can become the current accepted value."""


class FactTypeMismatchError(ValueError):
    """Fact type does not match the accepted-state slot being resolved."""


class ProjectionVersionConflictError(ValueError):
    """Accepted-state projection changed since the caller last read it."""
