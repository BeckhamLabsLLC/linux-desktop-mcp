"""Tests for window_manager module.

Pure Python tests — no mocks needed for most (dataclasses + enums).
"""

from unittest.mock import MagicMock

from linux_desktop_mcp.window_manager import (
    GroupColor,
    WindowGeometry,
    WindowGroup,
    WindowGroupManager,
    WindowTarget,
)

# ---------------------------------------------------------------------------
# GroupColor
# ---------------------------------------------------------------------------


class TestGroupColor:
    def test_from_string_known_colors(self):
        assert GroupColor.from_string("blue") is GroupColor.BLUE
        assert GroupColor.from_string("purple") is GroupColor.PURPLE
        assert GroupColor.from_string("green") is GroupColor.GREEN
        assert GroupColor.from_string("orange") is GroupColor.ORANGE
        assert GroupColor.from_string("red") is GroupColor.RED
        assert GroupColor.from_string("cyan") is GroupColor.CYAN

    def test_from_string_case_insensitive(self):
        assert GroupColor.from_string("BLUE") is GroupColor.BLUE
        assert GroupColor.from_string("Blue") is GroupColor.BLUE

    def test_from_string_unknown_defaults_to_blue(self):
        assert GroupColor.from_string("magenta") is GroupColor.BLUE
        assert GroupColor.from_string("") is GroupColor.BLUE

    def test_to_rgb_returns_floats(self):
        r, g, b = GroupColor.BLUE.to_rgb()
        assert 0.0 <= r <= 1.0
        assert 0.0 <= g <= 1.0
        assert 0.0 <= b <= 1.0

    def test_to_rgb_red(self):
        r, g, b = GroupColor.RED.to_rgb()
        assert r > 0.8  # Red channel dominant
        assert g < 0.3
        assert b < 0.3

    def test_hex_format(self):
        for color in GroupColor:
            assert color.value.startswith("#")
            assert len(color.value) == 7


# ---------------------------------------------------------------------------
# WindowGeometry
# ---------------------------------------------------------------------------


class TestWindowGeometry:
    def test_is_valid_normal(self):
        g = WindowGeometry(x=0, y=0, width=800, height=600)
        assert g.is_valid is True

    def test_is_valid_zero_width(self):
        g = WindowGeometry(x=0, y=0, width=0, height=600)
        assert g.is_valid is False

    def test_is_valid_zero_height(self):
        g = WindowGeometry(x=0, y=0, width=800, height=0)
        assert g.is_valid is False

    def test_is_valid_negative_dimensions(self):
        g = WindowGeometry(x=0, y=0, width=-1, height=600)
        assert g.is_valid is False

    def test_to_dict(self):
        g = WindowGeometry(x=10, y=20, width=300, height=400)
        d = g.to_dict()
        assert d == {"x": 10, "y": 20, "width": 300, "height": 400}

    def test_to_dict_keys_are_strings(self):
        d = WindowGeometry(x=0, y=0, width=1, height=1).to_dict()
        assert all(isinstance(k, str) for k in d)


# ---------------------------------------------------------------------------
# WindowTarget
# ---------------------------------------------------------------------------


class TestWindowTarget:
    def _make_target(self, **kwargs) -> WindowTarget:
        defaults = {
            "window_id": "win_1",
            "app_name": "Firefox",
            "window_title": "GitHub",
            "atspi_accessible": MagicMock(),
        }
        defaults.update(kwargs)
        return WindowTarget(**defaults)

    def test_to_dict_contains_keys(self):
        t = self._make_target()
        d = t.to_dict()
        assert "window_id" in d
        assert "app_name" in d
        assert "window_title" in d
        assert "is_active" in d

    def test_to_dict_geometry_none(self):
        t = self._make_target(geometry=None)
        assert t.to_dict()["geometry"] is None

    def test_to_dict_geometry_present(self):
        t = self._make_target(geometry=WindowGeometry(x=1, y=2, width=3, height=4))
        assert t.to_dict()["geometry"] == {"x": 1, "y": 2, "width": 3, "height": 4}

    def test_is_valid_with_mock_accessible(self):
        mock_acc = MagicMock()
        mock_acc.get_state_set.return_value = MagicMock()
        t = self._make_target(atspi_accessible=mock_acc)
        assert t.is_valid() is True

    def test_is_valid_none_accessible(self):
        t = self._make_target(atspi_accessible=None)
        assert t.is_valid() is False

    def test_is_valid_exception_means_invalid(self):
        mock_acc = MagicMock()
        mock_acc.get_state_set.side_effect = Exception("closed")
        t = self._make_target(atspi_accessible=mock_acc)
        assert t.is_valid() is False

    def test_default_is_active_false(self):
        t = self._make_target()
        assert t.is_active is False


# ---------------------------------------------------------------------------
# WindowGroup
# ---------------------------------------------------------------------------


class TestWindowGroup:
    def _make_target(self, wid: str = "win_1", **kwargs) -> WindowTarget:
        defaults = {
            "window_id": wid,
            "app_name": "App",
            "window_title": "Title",
            "atspi_accessible": MagicMock(),
        }
        defaults.update(kwargs)
        return WindowTarget(**defaults)

    def test_add_window_first_becomes_active(self):
        group = WindowGroup()
        t = self._make_target("win_1")
        group.add_window(t)
        assert group.active_window_id == "win_1"
        assert t.is_active is True

    def test_add_window_second_not_active(self):
        group = WindowGroup()
        group.add_window(self._make_target("win_1"))
        t2 = self._make_target("win_2")
        group.add_window(t2)
        assert t2.is_active is False
        assert group.active_window_id == "win_1"

    def test_remove_window_switches_active(self):
        group = WindowGroup()
        group.add_window(self._make_target("win_1"))
        group.add_window(self._make_target("win_2"))
        group.remove_window("win_1")
        assert group.active_window_id == "win_2"

    def test_remove_last_window_clears_active(self):
        group = WindowGroup()
        group.add_window(self._make_target("win_1"))
        group.remove_window("win_1")
        assert group.active_window_id is None

    def test_remove_nonexistent_returns_none(self):
        group = WindowGroup()
        assert group.remove_window("win_99") is None

    def test_set_active_window(self):
        group = WindowGroup()
        group.add_window(self._make_target("win_1"))
        group.add_window(self._make_target("win_2"))
        assert group.set_active_window("win_2") is True
        assert group.active_window_id == "win_2"

    def test_set_active_window_nonexistent(self):
        group = WindowGroup()
        assert group.set_active_window("win_99") is False

    def test_get_active_window(self):
        group = WindowGroup()
        t = self._make_target("win_1")
        group.add_window(t)
        assert group.get_active_window() is t

    def test_get_active_window_empty(self):
        group = WindowGroup()
        assert group.get_active_window() is None

    def test_validate_windows_removes_invalid(self):
        bad_acc = MagicMock()
        bad_acc.get_state_set.side_effect = Exception("gone")
        group = WindowGroup()
        group.add_window(self._make_target("win_1", atspi_accessible=bad_acc))
        removed = group.validate_windows()
        assert "win_1" in removed
        assert len(group.windows) == 0

    def test_validate_windows_keeps_valid(self):
        group = WindowGroup()
        group.add_window(self._make_target("win_1"))
        removed = group.validate_windows()
        assert removed == []
        assert len(group.windows) == 1

    def test_to_dict(self):
        group = WindowGroup(name="test")
        d = group.to_dict()
        assert d["name"] == "test"
        assert "group_id" in d
        assert "windows" in d

    def test_len(self):
        group = WindowGroup()
        assert len(group) == 0
        group.add_window(self._make_target("win_1"))
        assert len(group) == 1

    def test_get_all_windows(self):
        group = WindowGroup()
        group.add_window(self._make_target("win_1"))
        group.add_window(self._make_target("win_2"))
        assert len(group.get_all_windows()) == 2


# ---------------------------------------------------------------------------
# WindowGroupManager
# ---------------------------------------------------------------------------


class TestWindowGroupManager:
    def test_create_group(self):
        mgr = WindowGroupManager()
        group = mgr.create_group(name="test")
        assert group.name == "test"
        assert mgr.get_active_group() is group  # first becomes active

    def test_create_second_group_stays_first_active(self):
        mgr = WindowGroupManager()
        g1 = mgr.create_group(name="first")
        mgr.create_group(name="second")
        assert mgr.get_active_group() is g1

    def test_set_active_group(self):
        mgr = WindowGroupManager()
        mgr.create_group(name="first")
        g2 = mgr.create_group(name="second")
        mgr.set_active_group(g2.group_id)
        assert mgr.get_active_group() is g2

    def test_set_active_group_invalid(self):
        mgr = WindowGroupManager()
        assert mgr.set_active_group("nonexistent") is False

    def test_delete_group(self):
        mgr = WindowGroupManager()
        g = mgr.create_group()
        deleted = mgr.delete_group(g.group_id)
        assert deleted is g
        assert mgr.get_active_group() is None

    def test_delete_active_switches_to_remaining(self):
        mgr = WindowGroupManager()
        g1 = mgr.create_group()
        g2 = mgr.create_group()
        mgr.set_active_group(g1.group_id)
        mgr.delete_group(g1.group_id)
        assert mgr.get_active_group() is g2

    def test_get_or_create_active_group(self):
        mgr = WindowGroupManager()
        g = mgr.get_or_create_active_group()
        assert g is not None
        # Calling again returns same
        assert mgr.get_or_create_active_group() is g

    def test_add_window_to_active_group(self):
        mgr = WindowGroupManager()
        group, target = mgr.add_window_to_active_group(
            app_name="App", window_title="Win", atspi_accessible=MagicMock()
        )
        assert target.window_id.startswith("win_")
        assert target.window_id in group.windows

    def test_generate_window_id_unique(self):
        mgr = WindowGroupManager()
        ids = {mgr._generate_window_id() for _ in range(100)}
        assert len(ids) == 100

    def test_find_window_by_id(self):
        mgr = WindowGroupManager()
        _, target = mgr.add_window_to_active_group(
            app_name="A", window_title="W", atspi_accessible=MagicMock()
        )
        result = mgr.find_window_by_id(target.window_id)
        assert result is not None
        assert result[1] is target

    def test_find_window_by_id_not_found(self):
        mgr = WindowGroupManager()
        assert mgr.find_window_by_id("win_999") is None

    def test_release_window(self):
        mgr = WindowGroupManager()
        _, target = mgr.add_window_to_active_group(
            app_name="A", window_title="W", atspi_accessible=MagicMock()
        )
        released = mgr.release_window(target.window_id)
        assert released is target

    def test_release_window_not_found(self):
        mgr = WindowGroupManager()
        assert mgr.release_window("win_999") is None

    def test_release_all_windows(self):
        mgr = WindowGroupManager()
        mgr.add_window_to_active_group(
            app_name="A", window_title="W1", atspi_accessible=MagicMock()
        )
        mgr.add_window_to_active_group(
            app_name="A", window_title="W2", atspi_accessible=MagicMock()
        )
        count = mgr.release_all_windows()
        assert count == 2

    def test_clear(self):
        mgr = WindowGroupManager()
        mgr.add_window_to_active_group(app_name="A", window_title="W", atspi_accessible=MagicMock())
        mgr.clear()
        assert mgr.get_active_group() is None
        assert mgr.get_all_groups() == []

    def test_to_dict(self):
        mgr = WindowGroupManager()
        mgr.create_group(name="g")
        d = mgr.to_dict()
        assert "active_group_id" in d
        assert d["group_count"] == 1

    def test_get_all_groups(self):
        mgr = WindowGroupManager()
        mgr.create_group()
        mgr.create_group()
        assert len(mgr.get_all_groups()) == 2
