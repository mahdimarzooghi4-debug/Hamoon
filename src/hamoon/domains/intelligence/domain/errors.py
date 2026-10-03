class FeaturePackageBuildError(ValueError):
    """A safe, reproducible AI feature package cannot be built."""


class FeaturePackageNotFoundError(LookupError):
    """Requested feature package does not exist."""
