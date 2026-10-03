class OutcomePreparationError(ValueError):
    """Outcome inputs cannot be compared safely."""


class OutcomeReviewError(ValueError):
    """Outcome human review is invalid."""


class OutcomeVersionConflictError(ValueError):
    """Outcome changed since the reviewer loaded it."""



class OutcomeInterpretationError(ValueError):
    """AI outcome interpretation proposal cannot be generated safely."""
