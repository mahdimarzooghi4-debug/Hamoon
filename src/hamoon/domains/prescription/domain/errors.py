class PrescriptionGenerationError(ValueError):
    """A source-grounded prescription proposal could not be generated safely."""


class PrescriptionNotFoundError(LookupError):
    """Prescription does not exist."""
