"""Domain errors for local model package setup."""


class ModelInstallError(RuntimeError):
    """Raised when the local model package cannot be installed safely."""


class ModelInstallCancelled(ModelInstallError):
    """Raised when a user cancels a model download."""
