"""Shared domain/application exception types.

Kept outside `application/` so registries can raise them without
violating the layering contract (registry must not import application).
"""


class ThreadBusy(Exception):
    """Raised when a thread already has an active run."""


class UnknownRoute(Exception):
    """Raised when a registry key (route) is not registered."""


class RunNotFound(Exception):
    """Raised when cancel targets a missing run."""
