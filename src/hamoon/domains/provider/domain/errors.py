class ProviderMatchError(ValueError):
    """Provider matching could not be completed safely."""


class ProviderSelectionError(ValueError):
    """Provider selection is not valid for the recorded match."""
