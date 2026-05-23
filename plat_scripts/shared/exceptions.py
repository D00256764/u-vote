"""Shared exception hierarchy for U-Vote platform scripts."""


class PlatformError(Exception):
    """Base class for all U-Vote platform errors."""


class PreflightError(PlatformError):
    """Raised when a prerequisite check fails before a phase can begin."""


class DeploymentError(PlatformError):
    """Raised when a deployment phase fails and cannot continue."""


class StepTimeoutError(PlatformError):
    """Raised when a pod or rollout wait exceeds its timeout."""
