class InvalidPGORInputError(ValueError):
    """PGOR inputs cannot produce a deterministic valid calculation."""


class InvalidFormulaVersionError(ValueError):
    """Formula coefficients or activation state are invalid."""


class PGORCalculationBlockedError(ValueError):
    """Official PGOR calculation is blocked by readiness or policy."""


class FormulaVersionNotFoundError(LookupError):
    """Requested formula version does not exist."""


class PGORSnapshotNotFoundError(LookupError):
    """Requested PGOR snapshot does not exist."""
