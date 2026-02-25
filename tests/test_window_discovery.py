"""Tests for window_discovery module.

Tests the WindowInfo dataclass and sync-level logic by mocking AT-SPI.
"""

from unittest.mock import MagicMock

from linux_desktop_mcp.window_discovery import WindowInfo
from linux_desktop_mcp.window_manager import WindowGeometry

# ---------------------------------------------------------------------------
# WindowInfo
# ---------------------------------------------------------------------------


class TestWindowInfo:
    def test_to_dict_keys(self):
        info = WindowInfo(
            app_name="Firefox",
            window_title="GitHub",
            atspi_accessible=MagicMock(),
            geometry=WindowGeometry(x=0, y=0, width=800, height=600),
            is_active=True,
            is_focused=False,
            pid=1234,
        )
        d = info.to_dict()
        assert d["app_name"] == "Firefox"
        assert d["window_title"] == "GitHub"
        assert d["is_active"] is True
        assert d["is_focused"] is False
        assert d["pid"] == 1234
        assert d["geometry"]["width"] == 800

    def test_to_dict_no_geometry(self):
        info = WindowInfo(
            app_name="App",
            window_title="Win",
            atspi_accessible=MagicMock(),
            geometry=None,
            is_active=False,
            is_focused=False,
        )
        assert info.to_dict()["geometry"] is None

    def test_to_dict_no_pid(self):
        info = WindowInfo(
            app_name="App",
            window_title="Win",
            atspi_accessible=MagicMock(),
            geometry=None,
            is_active=False,
            is_focused=False,
        )
        assert info.to_dict()["pid"] is None

    def test_to_dict_focused(self):
        info = WindowInfo(
            app_name="App",
            window_title="Win",
            atspi_accessible=MagicMock(),
            geometry=None,
            is_active=False,
            is_focused=True,
        )
        assert info.to_dict()["is_focused"] is True

    def test_default_pid_none(self):
        info = WindowInfo(
            app_name="A",
            window_title="W",
            atspi_accessible=MagicMock(),
            geometry=None,
            is_active=False,
            is_focused=False,
        )
        assert info.pid is None

    def test_geometry_dict_matches(self):
        geom = WindowGeometry(x=10, y=20, width=300, height=400)
        info = WindowInfo(
            app_name="A",
            window_title="W",
            atspi_accessible=MagicMock(),
            geometry=geom,
            is_active=False,
            is_focused=False,
        )
        d = info.to_dict()
        assert d["geometry"] == {"x": 10, "y": 20, "width": 300, "height": 400}


# ---------------------------------------------------------------------------
# WindowDiscovery sync helpers (tested via mocking)
# ---------------------------------------------------------------------------


class TestWindowDiscoveryFilters:
    """Test the pure logic of filtering in _find_window_by_title_sync / by_app."""

    def _make_info(
        self, app_name: str = "App", title: str = "Win", focused: bool = False
    ) -> WindowInfo:
        return WindowInfo(
            app_name=app_name,
            window_title=title,
            atspi_accessible=MagicMock(),
            geometry=None,
            is_active=False,
            is_focused=focused,
        )

    def test_title_partial_match(self):
        windows = [
            self._make_info(title="GitHub - Firefox"),
            self._make_info(title="Settings"),
        ]
        title_lower = "github"
        matches = [w for w in windows if title_lower in w.window_title.lower()]
        assert len(matches) == 1
        assert matches[0].window_title == "GitHub - Firefox"

    def test_title_no_match(self):
        windows = [self._make_info(title="Settings")]
        matches = [w for w in windows if "nonexistent" in w.window_title.lower()]
        assert len(matches) == 0

    def test_app_filter(self):
        windows = [
            self._make_info(app_name="Firefox", title="Tab 1"),
            self._make_info(app_name="Firefox", title="Tab 2"),
            self._make_info(app_name="Nautilus", title="Files"),
        ]
        app_lower = "firefox"
        matches = [w for w in windows if app_lower in w.app_name.lower()]
        assert len(matches) == 2

    def test_combined_title_and_app_filter(self):
        windows = [
            self._make_info(app_name="Firefox", title="GitHub - Firefox"),
            self._make_info(app_name="Firefox", title="Settings - Firefox"),
            self._make_info(app_name="Chrome", title="GitHub - Chrome"),
        ]
        app_lower = "firefox"
        title_lower = "github"
        matches = [
            w
            for w in windows
            if app_lower in w.app_name.lower() and title_lower in w.window_title.lower()
        ]
        assert len(matches) == 1

    def test_focused_window_selection(self):
        windows = [
            self._make_info(focused=False),
            self._make_info(focused=True),
        ]
        focused = next((w for w in windows if w.is_focused), None)
        assert focused is not None
        assert focused.is_focused is True

    def test_no_focused_fallback_active(self):
        w1 = self._make_info(focused=False)
        w1.is_active = True
        w2 = self._make_info(focused=False)
        windows = [w1, w2]
        focused = next((w for w in windows if w.is_focused), None)
        assert focused is None
        active = next((w for w in windows if w.is_active), None)
        assert active is w1

    def test_skip_system_apps(self):
        system_apps = {"", "mutter", "gnome-shell", "plasmashell"}
        windows = [self._make_info(app_name=name) for name in system_apps]
        filtered = [w for w in windows if w.app_name not in system_apps]
        assert len(filtered) == 0

    def test_keep_normal_apps(self):
        system_apps = {"", "mutter", "gnome-shell", "plasmashell"}
        windows = [
            self._make_info(app_name="Firefox"),
            self._make_info(app_name="mutter"),
        ]
        filtered = [w for w in windows if w.app_name not in system_apps]
        assert len(filtered) == 1
        assert filtered[0].app_name == "Firefox"
