"""Domain errors for supported desktop application actions."""


class ApplicationLaunchError(RuntimeError):
    """Raised when an allowlisted application cannot be launched."""

