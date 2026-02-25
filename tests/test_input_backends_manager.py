"""Tests for InputManager and backend selection logic.

Mocks asyncio.create_subprocess_exec to avoid needing real input tools.
"""

from unittest.mock import AsyncMock, patch

import pytest

from linux_desktop_mcp.detection import DisplayServer, PlatformCapabilities
from linux_desktop_mcp.input_backends import (
    InputManager,
    WtypeBackend,
    XdotoolBackend,
    YdotoolBackend,
)

# ---------------------------------------------------------------------------
# InputManager backend selection
# ---------------------------------------------------------------------------


class TestInputManagerBackendSelection:
    def test_wayland_ydotool(self):
        caps = PlatformCapabilities(display_server=DisplayServer.WAYLAND, has_ydotool=True)
        mgr = InputManager(caps)
        assert mgr.backend_name == "ydotool"
        assert mgr.can_click is True
        assert mgr.can_type is True

    def test_wayland_wtype_only(self):
        caps = PlatformCapabilities(display_server=DisplayServer.WAYLAND, has_wtype=True)
        mgr = InputManager(caps)
        assert mgr.can_click is False  # wtype can't click
        assert mgr.can_type is True

    def test_wayland_no_tools(self):
        caps = PlatformCapabilities(display_server=DisplayServer.WAYLAND)
        mgr = InputManager(caps)
        assert mgr.can_click is False
        assert mgr.can_type is False

    def test_x11_xdotool(self):
        caps = PlatformCapabilities(display_server=DisplayServer.X11, has_xdotool=True)
        mgr = InputManager(caps)
        assert mgr.backend_name == "xdotool"
        assert mgr.can_click is True

    def test_x11_ydotool_fallback(self):
        caps = PlatformCapabilities(display_server=DisplayServer.X11, has_ydotool=True)
        mgr = InputManager(caps)
        assert mgr.backend_name == "ydotool"

    def test_x11_no_tools(self):
        caps = PlatformCapabilities(display_server=DisplayServer.X11)
        mgr = InputManager(caps)
        assert mgr.can_click is False
        assert mgr.can_type is False

    def test_x11_prefers_xdotool_over_ydotool(self):
        caps = PlatformCapabilities(
            display_server=DisplayServer.X11, has_xdotool=True, has_ydotool=True
        )
        mgr = InputManager(caps)
        assert mgr.backend_name == "xdotool"


# ---------------------------------------------------------------------------
# InputManager delegation
# ---------------------------------------------------------------------------


class TestInputManagerDelegation:
    @pytest.mark.asyncio
    async def test_click_no_backend(self):
        caps = PlatformCapabilities(display_server=DisplayServer.X11)
        mgr = InputManager(caps)
        result = await mgr.click(100, 200)
        assert result is False

    @pytest.mark.asyncio
    async def test_type_no_backend(self):
        caps = PlatformCapabilities(display_server=DisplayServer.X11)
        mgr = InputManager(caps)
        result = await mgr.type_text("hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_key_no_backend(self):
        caps = PlatformCapabilities(display_server=DisplayServer.X11)
        mgr = InputManager(caps)
        result = await mgr.key("Return")
        assert result is False

    @pytest.mark.asyncio
    async def test_move_no_backend(self):
        caps = PlatformCapabilities(display_server=DisplayServer.X11)
        mgr = InputManager(caps)
        result = await mgr.move(100, 200)
        assert result is False

    @pytest.mark.asyncio
    async def test_type_text_too_long(self):
        caps = PlatformCapabilities(display_server=DisplayServer.X11, has_xdotool=True)
        mgr = InputManager(caps)
        result = await mgr.type_text("x" * 10001)
        assert result is False


# ---------------------------------------------------------------------------
# YdotoolBackend
# ---------------------------------------------------------------------------


def _mock_subprocess_success():
    """Create a mock subprocess that returns success."""
    proc = AsyncMock()
    proc.returncode = 0
    proc.communicate = AsyncMock(return_value=(b"", b""))
    return proc


def _mock_subprocess_failure():
    """Create a mock subprocess that returns failure."""
    proc = AsyncMock()
    proc.returncode = 1
    proc.communicate = AsyncMock(return_value=(b"", b"error"))
    return proc


class TestYdotoolBackend:
    def test_button_map(self):
        assert YdotoolBackend.BUTTON_MAP["left"] == 0x110
        assert YdotoolBackend.BUTTON_MAP["right"] == 0x111
        assert YdotoolBackend.BUTTON_MAP["middle"] == 0x112

    def test_name(self):
        assert YdotoolBackend().name == "ydotool"

    @pytest.mark.asyncio
    async def test_move(self):
        backend = YdotoolBackend()
        with patch("asyncio.create_subprocess_exec", return_value=_mock_subprocess_success()):
            result = await backend.move(100, 200)
            assert result is True

    @pytest.mark.asyncio
    async def test_type_text(self):
        backend = YdotoolBackend()
        with patch("asyncio.create_subprocess_exec", return_value=_mock_subprocess_success()):
            result = await backend.type_text("hello")
            assert result is True

    @pytest.mark.asyncio
    async def test_key_with_modifiers(self):
        backend = YdotoolBackend()
        with patch("asyncio.create_subprocess_exec", return_value=_mock_subprocess_success()):
            result = await backend.key("c", ["ctrl"])
            assert result is True

    @pytest.mark.asyncio
    async def test_run_failure(self):
        backend = YdotoolBackend()
        with patch("asyncio.create_subprocess_exec", return_value=_mock_subprocess_failure()):
            result = await backend.move(0, 0)
            assert result is False

    @pytest.mark.asyncio
    async def test_run_os_error(self):
        backend = YdotoolBackend()
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            result = await backend.move(0, 0)
            assert result is False


# ---------------------------------------------------------------------------
# XdotoolBackend
# ---------------------------------------------------------------------------


class TestXdotoolBackend:
    def test_button_map(self):
        assert XdotoolBackend.BUTTON_MAP["left"] == "1"
        assert XdotoolBackend.BUTTON_MAP["right"] == "3"
        assert XdotoolBackend.BUTTON_MAP["middle"] == "2"

    def test_name(self):
        assert XdotoolBackend().name == "xdotool"

    @pytest.mark.asyncio
    async def test_type_text(self):
        backend = XdotoolBackend()
        with patch("asyncio.create_subprocess_exec", return_value=_mock_subprocess_success()):
            result = await backend.type_text("test")
            assert result is True

    @pytest.mark.asyncio
    async def test_key_simple(self):
        backend = XdotoolBackend()
        with patch("asyncio.create_subprocess_exec", return_value=_mock_subprocess_success()):
            result = await backend.key("Return")
            assert result is True

    @pytest.mark.asyncio
    async def test_key_with_modifiers(self):
        backend = XdotoolBackend()
        with patch("asyncio.create_subprocess_exec", return_value=_mock_subprocess_success()):
            result = await backend.key("s", ["ctrl"])
            assert result is True


# ---------------------------------------------------------------------------
# WtypeBackend
# ---------------------------------------------------------------------------


class TestWtypeBackend:
    def test_name(self):
        assert WtypeBackend().name == "wtype"

    @pytest.mark.asyncio
    async def test_click_returns_false(self):
        backend = WtypeBackend()
        result = await backend.click(100, 200)
        assert result is False

    @pytest.mark.asyncio
    async def test_move_returns_false(self):
        backend = WtypeBackend()
        result = await backend.move(100, 200)
        assert result is False

    @pytest.mark.asyncio
    async def test_type_text(self):
        backend = WtypeBackend()
        with patch("asyncio.create_subprocess_exec", return_value=_mock_subprocess_success()):
            result = await backend.type_text("hello")
            assert result is True

    @pytest.mark.asyncio
    async def test_key_with_modifiers(self):
        backend = WtypeBackend()
        with patch("asyncio.create_subprocess_exec", return_value=_mock_subprocess_success()):
            result = await backend.key("a", ["ctrl", "shift"])
            assert result is True
