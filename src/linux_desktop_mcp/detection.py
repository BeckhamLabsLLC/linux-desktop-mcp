"""Platform and capability detection for Linux desktop automation."""

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DisplayServer(Enum):
    """Linux display server types."""

    X11 = "x11"
    WAYLAND = "wayland"
    XWAYLAND = "xwayland"
    UNKNOWN = "unknown"


@dataclass
class PlatformCapabilities:
    """Available platform capabilities for desktop automation."""

    display_server: DisplayServer
    has_atspi: bool = False
    has_ydotool: bool = False
    has_xdotool: bool = False
    has_wtype: bool = False
    has_tesseract: bool = False
    has_grim: bool = False
    has_scrot: bool = False
    atspi_registry_available: bool = False
    has_layer_shell: bool = False  # wlr-layer-shell support
    compositor_name: Optional[str] = None  # Detected compositor
    errors: list[str] = field(default_factory=list)

    @property
    def can_discover_elements(self) -> bool:
        """Check if element discovery is possible."""
        return self.has_atspi and self.atspi_registry_available

    @property
    def can_simulate_input(self) -> bool:
        """Check if input simulation is possible."""
        if self.display_server == DisplayServer.WAYLAND:
            return self.has_ydotool or self.has_wtype
        return self.has_xdotool or self.has_ydotool

    @property
    def can_screenshot(self) -> bool:
        """Check if screenshots are possible."""
        if self.display_server == DisplayServer.WAYLAND:
            return self.has_grim
        return self.has_scrot or self.has_grim


def detect_display_server() -> DisplayServer:
    """Detect the current display server (X11, Wayland, or XWayland).

    Returns:
        DisplayServer enum indicating the active display server.
    """
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    wayland_display = os.environ.get("WAYLAND_DISPLAY")
    x_display = os.environ.get("DISPLAY")

    if session_type == "wayland" or wayland_display:
        if x_display:
            return DisplayServer.XWAYLAND
        return DisplayServer.WAYLAND
    elif session_type == "x11" or x_display:
        return DisplayServer.X11

    return DisplayServer.UNKNOWN


def _check_command_exists(command: str) -> bool:
    """Check if a command exists in PATH."""
    return shutil.which(command) is not None


def _check_atspi_available() -> tuple[bool, bool]:
    """Check if AT-SPI2 is available and the registry is running.

    Returns:
        Tuple of (pyatspi_available, registry_running).
    """
    pyatspi_available = False
    registry_running = False

    try:
        import gi

        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi

        pyatspi_available = True

        desktop = Atspi.get_desktop(0)
        if desktop is not None:
            registry_running = True
    except (ImportError, ValueError):
        pass
    except OSError:
        # D-Bus or GLib error when talking to the registry
        pyatspi_available = True

    return pyatspi_available, registry_running


def _check_ydotool_daemon() -> bool:
    """Check if ydotool daemon is running."""
    try:
        result = subprocess.run(["pgrep", "-x", "ydotoold"], capture_output=True, timeout=2)
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def _detect_compositor() -> Optional[str]:
    """Detect the Wayland compositor in use.

    Returns:
        Compositor name (sway, hyprland, gnome, kde, etc.) or None.
    """
    # Check common compositor indicators via environment variables
    if os.environ.get("SWAYSOCK"):
        return "sway"
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return "hyprland"
    if os.environ.get("GNOME_SETUP_DISPLAY") or os.environ.get("GNOME_SHELL_SESSION_MODE"):
        return "gnome"
    if os.environ.get("KDE_FULL_SESSION") or os.environ.get("KDE_SESSION_VERSION"):
        return "kde"
    if os.environ.get("WESTON_CONFIG_FILE"):
        return "weston"

    # Try to detect via XDG_CURRENT_DESKTOP
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if "gnome" in desktop:
        return "gnome"
    if "kde" in desktop or "plasma" in desktop:
        return "kde"
    if "sway" in desktop:
        return "sway"
    if "hyprland" in desktop:
        return "hyprland"

    return None


def _check_layer_shell_available() -> bool:
    """Check if gtk4-layer-shell is available and compositor supports it.

    Returns:
        True if layer shell overlays can be used.
    """
    try:
        import gi

        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gtk4LayerShell  # noqa: F401

        # Note: Gtk4LayerShell.is_supported() requires GTK to be initialized
        # So we just check if the import works (import is intentionally unused)
        return True
    except (ImportError, ValueError):
        return False


def detect_capabilities() -> PlatformCapabilities:
    """Detect all available platform capabilities.

    Returns:
        PlatformCapabilities with detected features.
    """
    display_server = detect_display_server()
    atspi_available, registry_running = _check_atspi_available()
    compositor = _detect_compositor() if display_server != DisplayServer.X11 else None
    layer_shell = _check_layer_shell_available() if display_server != DisplayServer.X11 else False

    caps = PlatformCapabilities(
        display_server=display_server,
        has_atspi=atspi_available,
        atspi_registry_available=registry_running,
        has_ydotool=_check_command_exists("ydotool"),
        has_xdotool=_check_command_exists("xdotool"),
        has_wtype=_check_command_exists("wtype"),
        has_tesseract=_check_command_exists("tesseract"),
        has_grim=_check_command_exists("grim"),
        has_scrot=_check_command_exists("scrot"),
        has_layer_shell=layer_shell,
        compositor_name=compositor,
    )

    if not caps.has_atspi:
        caps.errors.append(
            "AT-SPI2 not available. Install: sudo apt install python3-pyatspi gir1.2-atspi-2.0"
        )
    elif not caps.atspi_registry_available:
        caps.errors.append(
            "AT-SPI2 registry not running. Ensure at-spi2-core is installed and accessibility is enabled."
        )

    if display_server == DisplayServer.WAYLAND:
        if not caps.has_ydotool and not caps.has_wtype:
            caps.errors.append("No Wayland input tool available. Install ydotool or wtype.")
        elif caps.has_ydotool and not _check_ydotool_daemon():
            caps.errors.append("ydotool daemon not running. Start with: sudo ydotoold")
    elif display_server == DisplayServer.X11:
        if not caps.has_xdotool and not caps.has_ydotool:
            caps.errors.append("No X11 input tool available. Install: sudo apt install xdotool")

    return caps


def get_best_input_backend(caps: PlatformCapabilities) -> Optional[str]:
    """Determine the best input backend for the current platform.

    Args:
        caps: Platform capabilities.

    Returns:
        Name of the best input backend, or None if none available.
    """
    if caps.display_server == DisplayServer.WAYLAND:
        if caps.has_ydotool:
            return "ydotool"
        if caps.has_wtype:
            return "wtype"
    else:
        if caps.has_xdotool:
            return "xdotool"
        if caps.has_ydotool:
            return "ydotool"

    return None


def get_best_screenshot_backend(caps: PlatformCapabilities) -> Optional[str]:
    """Determine the best screenshot backend for the current platform.

    Args:
        caps: Platform capabilities.

    Returns:
        Name of the best screenshot backend, or None if none available.
    """
    if caps.display_server == DisplayServer.WAYLAND:
        if caps.has_grim:
            return "grim"
    else:
        if caps.has_scrot:
            return "scrot"
        if caps.has_grim:
            return "grim"

    return None
