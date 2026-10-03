class FeaturePackageBuildError(ValueError):
    """A safe, reproducible AI feature package cannot be built."""


class FeaturePackageNotFoundError(LookupError):
    """Requested feature package does not exist."""


class DiagnosisGenerationError(ValueError):
    """A diagnosis proposal could not be generated safely."""


class DiagnosisNotFoundError(LookupError):
    """Diagnosis does not exist."""


class AIDecisionNotFoundError(LookupError):
    """AI decision does not exist."""


class DiagnosisVersionConflictError(ValueError):
    """Diagnosis changed since it was read."""


class InvalidDiagnosisReviewError(ValueError):
    """Human review payload or transition is invalid."""
