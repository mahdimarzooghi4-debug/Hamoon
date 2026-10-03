class AssessmentNotFoundError(LookupError):
    """Assessment does not exist."""


class DefinitionNotAvailableError(LookupError):
    """Requested PGOR definition is not available."""


class IndicatorNotInDefinitionError(ValueError):
    """Indicator is not part of the assessment definition version."""


class InvalidObservationScoreError(ValueError):
    """Indicator observation score is outside the source-defined 0..100 range."""


class ObservationNotFoundError(LookupError):
    """Indicator observation does not exist in this assessment."""


class InvalidObservationValidationTransitionError(ValueError):
    """Observation validation transition is invalid."""


class ObservationNotValidatedError(ValueError):
    """Only a validated observation can become the accepted indicator value."""


class AcceptedObservationVersionConflictError(ValueError):
    """Accepted-observation projection changed since it was read."""


class ValidationVersionConflictError(ValueError):
    """Observation validation state changed since it was read."""
