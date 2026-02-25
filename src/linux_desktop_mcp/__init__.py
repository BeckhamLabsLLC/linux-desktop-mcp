"""Linux Desktop Automation MCP Server.

Provides Chrome-extension-level semantic element targeting for native Linux
desktop applications using AT-SPI2 (Assistive Technology Service Provider Interface).
"""

__version__ = "0.2.0"

from .exceptions import (
    ATSPIActionError,
    ATSPIError,
    ATSPINotAvailableError,
    ATSPITreeBuildError,
    DisplayServerError,
    GtkInitError,
    InputBackendNotAvailableError,
    InputCommandError,
    InputError,
    InputValidationError,
    LinuxDesktopMCPError,
    OverlayError,
    ReferenceExpiredError,
    ReferenceNotFoundError,
    WindowInvalidError,
    WindowNotFoundError,
)


def main() -> None:
    """Entry point for the MCP server."""
    from .server import main as _main

    _main()


__all__ = [
    "main",
    "__version__",
    "LinuxDesktopMCPError",
    "ATSPIError",
    "ATSPINotAvailableError",
    "ATSPITreeBuildError",
    "ATSPIActionError",
    "WindowNotFoundError",
    "WindowInvalidError",
    "ReferenceNotFoundError",
    "ReferenceExpiredError",
    "InputError",
    "InputBackendNotAvailableError",
    "InputCommandError",
    "InputValidationError",
    "OverlayError",
    "GtkInitError",
    "DisplayServerError",
]
