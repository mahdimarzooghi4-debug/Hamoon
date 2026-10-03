class LearningCurationError(ValueError):
    """Learning signal cannot be curated as requested."""


class LearningDatasetError(ValueError):
    """Learning dataset cannot be created or approved."""


class LearningDatasetVersionConflictError(ValueError):
    """Dataset changed since the caller loaded it."""
