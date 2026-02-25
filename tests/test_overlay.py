"""Tests for overlay module.

Tests NoOverlayBackend (pure Python) and OverlayManager backend selection logic.
"""

from linux_desktop_mcp.overlay import NoOverlayBackend
from linux_desktop_mcp.window_manager import GroupColor, WindowGeometry

# ---------------------------------------------------------------------------
# NoOverlayBackend
# ---------------------------------------------------------------------------


class TestNoOverlayBackend:
    def test_is_available(self):
        backend = NoOverlayBackend()
        assert backend.is_available() is False

    def test_show_border_returns_false(self):
        backend = NoOverlayBackend()
        geom = WindowGeometry(x=0, y=0, width=800, height=600)
        assert backend.show_border("win_1", geom, GroupColor.BLUE) is False

    def test_hide_border_returns_true(self):
        backend = NoOverlayBackend()
        assert backend.hide_border("win_1") is True

    def test_hide_all_borders_no_error(self):
        backend = NoOverlayBackend()
        backend.hide_all_borders()  # Should not raise

    def test_update_border_position_returns_false(self):
        backend = NoOverlayBackend()
        geom = WindowGeometry(x=0, y=0, width=800, height=600)
        assert backend.update_border_position("win_1", geom) is False

    def test_custom_reason(self):
        backend = NoOverlayBackend(reason="GNOME Wayland")
        assert backend._reason == "GNOME Wayland"

    def test_default_reason(self):
        backend = NoOverlayBackend()
        assert "No overlay support" in backend._reason


# ---------------------------------------------------------------------------
# OverlayManager backend selection
# ---------------------------------------------------------------------------


class TestOverlayManagerBackendSelection:
    def test_unknown_display_gets_no_overlay(self):
        from linux_desktop_mcp.detection import DisplayServer
        from linux_desktop_mcp.overlay import OverlayManager

        mgr = OverlayManager(DisplayServer.UNKNOWN)
        assert mgr.has_visual_support is False

    def test_wayland_without_layer_shell_gets_no_overlay(self):
        from linux_desktop_mcp.detection import DisplayServer
        from linux_desktop_mcp.overlay import OverlayManager

        mgr = OverlayManager(DisplayServer.WAYLAND)
        assert isinstance(mgr.backend, NoOverlayBackend)

    def test_show_border_delegates_to_backend(self):
        from linux_desktop_mcp.detection import DisplayServer
        from linux_desktop_mcp.overlay import OverlayManager

        mgr = OverlayManager(DisplayServer.UNKNOWN)
        geom = WindowGeometry(x=0, y=0, width=800, height=600)
        assert mgr.show_border("win_1", geom, GroupColor.BLUE) is False

    def test_hide_border_delegates(self):
        from linux_desktop_mcp.detection import DisplayServer
        from linux_desktop_mcp.overlay import OverlayManager

        mgr = OverlayManager(DisplayServer.UNKNOWN)
        assert mgr.hide_border("win_1") is True  # NoOverlay returns True

    def test_hide_all_borders_delegates(self):
        from linux_desktop_mcp.detection import DisplayServer
        from linux_desktop_mcp.overlay import OverlayManager

        mgr = OverlayManager(DisplayServer.UNKNOWN)
        mgr.hide_all_borders()  # Should not raise
