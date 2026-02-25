"""Custom exception hierarchy for linux-desktop-mcp.

Provides specific exception types to replace bare ``except Exception`` catches,
enabling callers to handle different failure modes appropriately.
"""


class LinuxDesktopMCPError(Exception):
    """Base exception for all linux-desktop-mcp errors."""


# -- AT-SPI errors ----------------------------------------------------------


class ATSPIError(LinuxDesktopMCPError):
    """Base class for AT-SPI related errors."""


class ATSPINotAvailableError(ATSPIError):
    """AT-SPI2 library or registry is not available."""


class ATSPITreeBuildError(ATSPIError):
    """Failed to build or traverse the accessibility tree."""


class ATSPIActionError(ATSPIError):
    """Failed to perform an AT-SPI action (click, focus, set text)."""


# -- Window errors -----------------------------------------------------------


class WindowNotFoundError(LinuxDesktopMCPError):
    """Requested window could not be found."""


class WindowInvalidError(LinuxDesktopMCPError):
    """Window exists but is in an invalid state (e.g. closed, no geometry)."""


# -- Reference errors --------------------------------------------------------


class ReferenceNotFoundError(LinuxDesktopMCPError):
    """Element reference ID was not found in the reference manager."""


class ReferenceExpiredError(ReferenceNotFoundError):
    """Element reference existed but has expired (TTL exceeded)."""


# -- Input errors ------------------------------------------------------------


class InputError(LinuxDesktopMCPError):
    """Base class for input simulation errors."""


class InputBackendNotAvailableError(InputError):
    """No suitable input backend is available."""


class InputCommandError(InputError):
    """An input backend command failed to execute."""


class InputValidationError(InputError):
    """Input parameters failed validation."""


# -- Overlay errors ----------------------------------------------------------


class OverlayError(LinuxDesktopMCPError):
    """Base class for overlay/border errors."""


class GtkInitError(OverlayError):
    """GTK initialization failed."""


# -- Display server errors ---------------------------------------------------


class DisplayServerError(LinuxDesktopMCPError):
    """Display server detection or interaction failed."""
