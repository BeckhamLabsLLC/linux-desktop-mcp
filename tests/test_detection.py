"""Tests for detection module.

Mocks os.environ and shutil.which to test display server / capability detection.
"""

from unittest.mock import patch

from linux_desktop_mcp.detection import (
    DisplayServer,
    PlatformCapabilities,
    _check_command_exists,
    _detect_compositor,
    detect_display_server,
)

# ---------------------------------------------------------------------------
# PlatformCapabilities properties
# ---------------------------------------------------------------------------


class TestPlatformCapabilities:
    def test_can_discover_elements_true(self):
        caps = PlatformCapabilities(
            display_server=DisplayServer.X11, has_atspi=True, atspi_registry_available=True
        )
        assert caps.can_discover_elements is True

    def test_can_discover_elements_no_atspi(self):
        caps = PlatformCapabilities(
            display_server=DisplayServer.X11, has_atspi=False, atspi_registry_available=True
        )
        assert caps.can_discover_elements is False

    def test_can_discover_elements_no_registry(self):
        caps = PlatformCapabilities(
            display_server=DisplayServer.X11, has_atspi=True, atspi_registry_available=False
        )
        assert caps.can_discover_elements is False

    def test_can_simulate_input_wayland_ydotool(self):
        caps = PlatformCapabilities(display_server=DisplayServer.WAYLAND, has_ydotool=True)
        assert caps.can_simulate_input is True

    def test_can_simulate_input_wayland_wtype(self):
        caps = PlatformCapabilities(display_server=DisplayServer.WAYLAND, has_wtype=True)
        assert caps.can_simulate_input is True

    def test_can_simulate_input_wayland_none(self):
        caps = PlatformCapabilities(display_server=DisplayServer.WAYLAND)
        assert caps.can_simulate_input is False

    def test_can_simulate_input_x11_xdotool(self):
        caps = PlatformCapabilities(display_server=DisplayServer.X11, has_xdotool=True)
        assert caps.can_simulate_input is True

    def test_can_simulate_input_x11_ydotool(self):
        caps = PlatformCapabilities(display_server=DisplayServer.X11, has_ydotool=True)
        assert caps.can_simulate_input is True

    def test_can_simulate_input_x11_none(self):
        caps = PlatformCapabilities(display_server=DisplayServer.X11)
        assert caps.can_simulate_input is False

    def test_can_screenshot_wayland_grim(self):
        caps = PlatformCapabilities(display_server=DisplayServer.WAYLAND, has_grim=True)
        assert caps.can_screenshot is True

    def test_can_screenshot_wayland_no_grim(self):
        caps = PlatformCapabilities(display_server=DisplayServer.WAYLAND)
        assert caps.can_screenshot is False

    def test_can_screenshot_x11_scrot(self):
        caps = PlatformCapabilities(display_server=DisplayServer.X11, has_scrot=True)
        assert caps.can_screenshot is True

    def test_can_screenshot_x11_grim(self):
        caps = PlatformCapabilities(display_server=DisplayServer.X11, has_grim=True)
        assert caps.can_screenshot is True

    def test_can_screenshot_x11_none(self):
        caps = PlatformCapabilities(display_server=DisplayServer.X11)
        assert caps.can_screenshot is False


# ---------------------------------------------------------------------------
# detect_display_server
# ---------------------------------------------------------------------------


class TestDetectDisplayServer:
    def test_wayland_session_with_display(self):
        env = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-0"}
        with patch.dict("os.environ", env, clear=True):
            assert detect_display_server() == DisplayServer.WAYLAND

    def test_wayland_display_only(self):
        env = {"WAYLAND_DISPLAY": "wayland-0"}
        with patch.dict("os.environ", env, clear=True):
            assert detect_display_server() == DisplayServer.WAYLAND

    def test_xwayland(self):
        env = {
            "XDG_SESSION_TYPE": "wayland",
            "WAYLAND_DISPLAY": "wayland-0",
            "DISPLAY": ":0",
        }
        with patch.dict("os.environ", env, clear=True):
            assert detect_display_server() == DisplayServer.XWAYLAND

    def test_x11_session(self):
        env = {"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"}
        with patch.dict("os.environ", env, clear=True):
            assert detect_display_server() == DisplayServer.X11

    def test_x11_display_only(self):
        env = {"DISPLAY": ":0"}
        with patch.dict("os.environ", env, clear=True):
            assert detect_display_server() == DisplayServer.X11

    def test_unknown_no_vars(self):
        with patch.dict("os.environ", {}, clear=True):
            assert detect_display_server() == DisplayServer.UNKNOWN

    def test_wayland_no_x_display(self):
        env = {"XDG_SESSION_TYPE": "wayland"}
        with patch.dict("os.environ", env, clear=True):
            assert detect_display_server() == DisplayServer.WAYLAND


# ---------------------------------------------------------------------------
# _detect_compositor
# ---------------------------------------------------------------------------


class TestDetectCompositor:
    def test_sway(self):
        with patch.dict("os.environ", {"SWAYSOCK": "/run/sway"}, clear=True):
            assert _detect_compositor() == "sway"

    def test_hyprland(self):
        with patch.dict("os.environ", {"HYPRLAND_INSTANCE_SIGNATURE": "abc"}, clear=True):
            assert _detect_compositor() == "hyprland"

    def test_gnome_setup(self):
        with patch.dict("os.environ", {"GNOME_SETUP_DISPLAY": ":99"}, clear=True):
            assert _detect_compositor() == "gnome"

    def test_gnome_shell_mode(self):
        with patch.dict("os.environ", {"GNOME_SHELL_SESSION_MODE": "ubuntu"}, clear=True):
            assert _detect_compositor() == "gnome"

    def test_kde_full_session(self):
        with patch.dict("os.environ", {"KDE_FULL_SESSION": "true"}, clear=True):
            assert _detect_compositor() == "kde"

    def test_kde_session_version(self):
        with patch.dict("os.environ", {"KDE_SESSION_VERSION": "6"}, clear=True):
            assert _detect_compositor() == "kde"

    def test_weston(self):
        with patch.dict("os.environ", {"WESTON_CONFIG_FILE": "/etc/weston"}, clear=True):
            assert _detect_compositor() == "weston"

    def test_xdg_current_desktop_gnome(self):
        with patch.dict("os.environ", {"XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}, clear=True):
            assert _detect_compositor() == "gnome"

    def test_xdg_current_desktop_kde(self):
        with patch.dict("os.environ", {"XDG_CURRENT_DESKTOP": "KDE"}, clear=True):
            assert _detect_compositor() == "kde"

    def test_xdg_current_desktop_sway(self):
        with patch.dict("os.environ", {"XDG_CURRENT_DESKTOP": "sway"}, clear=True):
            assert _detect_compositor() == "sway"

    def test_xdg_current_desktop_hyprland(self):
        with patch.dict("os.environ", {"XDG_CURRENT_DESKTOP": "Hyprland"}, clear=True):
            assert _detect_compositor() == "hyprland"

    def test_xdg_current_desktop_plasma(self):
        with patch.dict("os.environ", {"XDG_CURRENT_DESKTOP": "plasma"}, clear=True):
            assert _detect_compositor() == "kde"

    def test_unknown(self):
        with patch.dict("os.environ", {}, clear=True):
            assert _detect_compositor() is None


# ---------------------------------------------------------------------------
# _check_command_exists
# ---------------------------------------------------------------------------


class TestCheckCommandExists:
    def test_command_found(self):
        with patch("shutil.which", return_value="/usr/bin/xdotool"):
            assert _check_command_exists("xdotool") is True

    def test_command_not_found(self):
        with patch("shutil.which", return_value=None):
            assert _check_command_exists("nonexistent") is False
