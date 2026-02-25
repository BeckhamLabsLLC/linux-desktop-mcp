"""Tests for the MCP server module and handler functions.

MCP module mocks are loaded via conftest.py.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from linux_desktop_mcp.handlers import (
    MAX_COORDINATE,
    MAX_QUERY_LENGTH,
    MAX_TEXT_LENGTH,
    MIN_COORDINATE,
    ServerContext,
    handle_capabilities,
    handle_click,
    handle_context,
    handle_create_window_group,
    handle_find,
    handle_key,
    handle_release_window,
    handle_snapshot,
    handle_target_window,
    handle_type,
)
from linux_desktop_mcp.references import (
    ElementBounds,
    ElementReference,
    ElementRole,
    ElementState,
)

# ---------------------------------------------------------------------------
# Original validation / constant tests (kept for backwards compat)
# ---------------------------------------------------------------------------


class TestInputValidationFunctions:
    def test_coordinate_validation_logic(self):
        assert 0 >= MIN_COORDINATE and 0 <= MAX_COORDINATE
        assert 100 >= MIN_COORDINATE and 100 <= MAX_COORDINATE
        assert MAX_COORDINATE >= MIN_COORDINATE and MAX_COORDINATE <= MAX_COORDINATE
        assert -1 < MIN_COORDINATE
        assert MAX_COORDINATE + 1 > MAX_COORDINATE

    def test_string_validation_logic(self):
        assert len("hello") <= MAX_TEXT_LENGTH
        assert len("a" * MAX_TEXT_LENGTH) <= MAX_TEXT_LENGTH
        assert len("a" * (MAX_TEXT_LENGTH + 1)) > MAX_TEXT_LENGTH
        assert len("a" * (MAX_QUERY_LENGTH + 1)) > MAX_QUERY_LENGTH


class TestServerConstants:
    def test_max_text_length(self):
        assert MAX_TEXT_LENGTH == 10000

    def test_max_query_length(self):
        assert MAX_QUERY_LENGTH == 1000

    def test_coordinate_bounds(self):
        assert MIN_COORDINATE == 0
        assert MAX_COORDINATE == 65535


class TestValidationHelpers:
    """Test ServerContext validation methods."""

    def setup_method(self):
        self.ctx = ServerContext()

    def test_validate_coordinate_valid(self):
        assert self.ctx.validate_coordinate(0) is True
        assert self.ctx.validate_coordinate(100) is True
        assert self.ctx.validate_coordinate(65535) is True

    def test_validate_coordinate_invalid_negative(self):
        assert self.ctx.validate_coordinate(-1) is False

    def test_validate_coordinate_invalid_overflow(self):
        assert self.ctx.validate_coordinate(65536) is False

    def test_validate_coordinates_valid(self):
        is_valid, error = self.ctx.validate_coordinates(100, 200)
        assert is_valid is True
        assert error == ""

    def test_validate_coordinates_invalid_x(self):
        is_valid, error = self.ctx.validate_coordinates(-1, 100)
        assert is_valid is False
        assert "X coordinate" in error

    def test_validate_coordinates_invalid_y(self):
        is_valid, error = self.ctx.validate_coordinates(100, -1)
        assert is_valid is False
        assert "Y coordinate" in error

    def test_validate_coordinates_non_numeric(self):
        is_valid, error = self.ctx.validate_coordinates("abc", 100)
        assert is_valid is False
        assert "must be numbers" in error

    def test_validate_string_valid(self):
        is_valid, error = self.ctx.validate_string("hello", 100, "test")
        assert is_valid is True
        assert error == ""

    def test_validate_string_too_long(self):
        is_valid, error = self.ctx.validate_string("a" * 101, 100, "test")
        assert is_valid is False
        assert "too long" in error

    def test_validate_string_non_string(self):
        is_valid, error = self.ctx.validate_string(123, 100, "test")
        assert is_valid is False
        assert "must be a string" in error


# ---------------------------------------------------------------------------
# Handler tests
# ---------------------------------------------------------------------------


def _make_ref(
    ref_id="ref_1",
    name="Test Button",
    role=ElementRole.BUTTON,
    actions=None,
    editable=False,
    accessible=None,
) -> ElementReference:
    return ElementReference(
        ref_id=ref_id,
        source="atspi",
        role=role,
        name=name,
        bounds=ElementBounds(x=100, y=100, width=50, height=30),
        state=ElementState(editable=editable),
        available_actions=actions or [],
        atspi_accessible=accessible or MagicMock(),
    )


class TestHandleSnapshot:
    @pytest.mark.asyncio
    async def test_no_bridge(self, server_ctx):
        server_ctx.bridge = None
        result = await handle_snapshot(server_ctx, {})
        assert "AT-SPI2 not available" in result[0].text

    @pytest.mark.asyncio
    async def test_empty_tree(self, server_ctx):
        server_ctx.bridge.build_tree = AsyncMock(return_value=[])
        result = await handle_snapshot(server_ctx, {})
        assert "No elements found" in result[0].text

    @pytest.mark.asyncio
    async def test_with_elements(self, server_ctx):
        ref = _make_ref()
        server_ctx.bridge.build_tree = AsyncMock(return_value=[ref])
        server_ctx.bridge.ref_manager.add(ref)
        result = await handle_snapshot(server_ctx, {})
        assert "ref_1" in result[0].text

    @pytest.mark.asyncio
    async def test_app_filter(self, server_ctx):
        ref = _make_ref()
        server_ctx.bridge.build_tree = AsyncMock(return_value=[ref])
        server_ctx.bridge.ref_manager.add(ref)
        result = await handle_snapshot(server_ctx, {"app_name": "Firefox"})
        assert "Filtered by app: Firefox" in result[0].text


class TestHandleFind:
    @pytest.mark.asyncio
    async def test_no_bridge(self, server_ctx):
        server_ctx.bridge = None
        result = await handle_find(server_ctx, {"query": "button"})
        assert "AT-SPI2 not available" in result[0].text

    @pytest.mark.asyncio
    async def test_empty_query(self, server_ctx):
        result = await handle_find(server_ctx, {"query": ""})
        assert "empty" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_query_too_long(self, server_ctx):
        result = await handle_find(server_ctx, {"query": "x" * 1001})
        assert "too long" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_no_matches(self, server_ctx):
        server_ctx.bridge.build_tree = AsyncMock(return_value=[])
        result = await handle_find(server_ctx, {"query": "nonexistent"})
        assert "No elements found" in result[0].text

    @pytest.mark.asyncio
    async def test_with_matches(self, server_ctx):
        ref = _make_ref(name="Save Button")
        server_ctx.bridge.build_tree = AsyncMock(return_value=[ref])
        server_ctx.bridge.ref_manager.add(ref)
        result = await handle_find(server_ctx, {"query": "Save"})
        assert "Save Button" in result[0].text


class TestHandleClick:
    @pytest.mark.asyncio
    async def test_no_bridge(self, server_ctx):
        server_ctx.bridge = None
        result = await handle_click(server_ctx, {"ref": "ref_1"})
        assert "AT-SPI2 not available" in result[0].text

    @pytest.mark.asyncio
    async def test_ref_not_found(self, server_ctx):
        result = await handle_click(server_ctx, {"ref": "ref_999"})
        assert "not found or expired" in result[0].text

    @pytest.mark.asyncio
    async def test_click_by_ref_atspi_action(self, server_ctx):
        ref = _make_ref(actions=["click"])
        server_ctx.bridge.ref_manager.add(ref)
        server_ctx.bridge.click_element = AsyncMock(return_value=True)
        result = await handle_click(server_ctx, {"ref": "ref_1", "element": "button"})
        assert "via AT-SPI action" in result[0].text

    @pytest.mark.asyncio
    async def test_click_by_coordinate(self, server_ctx):
        server_ctx.input.click = AsyncMock(return_value=True)
        result = await handle_click(server_ctx, {"coordinate": [100, 200]})
        assert "Clicked at (100, 200)" in result[0].text

    @pytest.mark.asyncio
    async def test_click_invalid_coordinate(self, server_ctx):
        result = await handle_click(server_ctx, {"coordinate": [-1, 200]})
        assert "Error" in result[0].text

    @pytest.mark.asyncio
    async def test_click_no_ref_no_coord(self, server_ctx):
        result = await handle_click(server_ctx, {})
        assert "Provide either ref or coordinate" in result[0].text

    @pytest.mark.asyncio
    async def test_click_coordinate_wrong_length(self, server_ctx):
        result = await handle_click(server_ctx, {"coordinate": [100]})
        assert "must be [x, y]" in result[0].text

    @pytest.mark.asyncio
    async def test_click_by_ref_fallback_to_input(self, server_ctx):
        ref = _make_ref(actions=[])
        server_ctx.bridge.ref_manager.add(ref)
        server_ctx.input.click_element = AsyncMock(return_value=True)
        result = await handle_click(server_ctx, {"ref": "ref_1"})
        assert "Clicked" in result[0].text


class TestHandleType:
    @pytest.mark.asyncio
    async def test_no_input(self, server_ctx):
        server_ctx.input = None
        result = await handle_type(server_ctx, {"text": "hello"})
        assert "No keyboard input" in result[0].text

    @pytest.mark.asyncio
    async def test_success(self, server_ctx):
        server_ctx.input.type_text = AsyncMock(return_value=True)
        result = await handle_type(server_ctx, {"text": "hello"})
        assert "Typed text" in result[0].text

    @pytest.mark.asyncio
    async def test_with_ref(self, server_ctx):
        ref = _make_ref(editable=True)
        server_ctx.bridge.ref_manager.add(ref)
        server_ctx.bridge.set_text = AsyncMock(return_value=True)
        result = await handle_type(server_ctx, {"text": "hello", "ref": "ref_1"})
        assert "via AT-SPI" in result[0].text

    @pytest.mark.asyncio
    async def test_text_too_long(self, server_ctx):
        result = await handle_type(server_ctx, {"text": "x" * 10001})
        assert "too long" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_submit(self, server_ctx):
        server_ctx.input.type_text = AsyncMock(return_value=True)
        server_ctx.input.key = AsyncMock(return_value=True)
        result = await handle_type(server_ctx, {"text": "hello", "submit": True})
        assert "pressed Enter" in result[0].text

    @pytest.mark.asyncio
    async def test_clear_first(self, server_ctx):
        server_ctx.input.type_text = AsyncMock(return_value=True)
        server_ctx.input.key = AsyncMock(return_value=True)
        result = await handle_type(server_ctx, {"text": "hello", "clear_first": True})
        assert "Typed text" in result[0].text

    @pytest.mark.asyncio
    async def test_ref_not_found(self, server_ctx):
        result = await handle_type(server_ctx, {"text": "hello", "ref": "ref_999"})
        assert "not found or expired" in result[0].text


class TestHandleKey:
    @pytest.mark.asyncio
    async def test_no_input(self, server_ctx):
        server_ctx.input = None
        result = await handle_key(server_ctx, {"key": "Return"})
        assert "No keyboard input" in result[0].text

    @pytest.mark.asyncio
    async def test_success(self, server_ctx):
        server_ctx.input.key = AsyncMock(return_value=True)
        result = await handle_key(server_ctx, {"key": "Return"})
        assert "Pressed Return" in result[0].text

    @pytest.mark.asyncio
    async def test_with_modifiers(self, server_ctx):
        server_ctx.input.key = AsyncMock(return_value=True)
        result = await handle_key(server_ctx, {"key": "c", "modifiers": ["ctrl"]})
        assert "ctrl+c" in result[0].text

    @pytest.mark.asyncio
    async def test_empty_key(self, server_ctx):
        result = await handle_key(server_ctx, {"key": ""})
        assert "required" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_key_too_long(self, server_ctx):
        result = await handle_key(server_ctx, {"key": "x" * 51})
        assert "too long" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_key_failure(self, server_ctx):
        server_ctx.input.key = AsyncMock(return_value=False)
        result = await handle_key(server_ctx, {"key": "Return"})
        assert "Failed" in result[0].text


class TestHandleCapabilities:
    @pytest.mark.asyncio
    async def test_returns_info(self, server_ctx):
        result = await handle_capabilities(server_ctx, {})
        text = result[0].text
        assert "Display Server" in text
        assert "AT-SPI2 Available" in text
        assert "Input Tools" in text


class TestHandleContext:
    @pytest.mark.asyncio
    async def test_no_group(self, server_ctx):
        result = await handle_context(server_ctx, {})
        assert "No active window group" in result[0].text

    @pytest.mark.asyncio
    async def test_with_group(self, server_ctx):
        server_ctx.window_manager.add_window_to_active_group(
            app_name="App", window_title="Win", atspi_accessible=MagicMock()
        )
        result = await handle_context(server_ctx, {})
        assert "Active Window Group" in result[0].text
        assert "Win" in result[0].text

    @pytest.mark.asyncio
    async def test_list_available_no_discovery(self, server_ctx):
        result = await handle_context(server_ctx, {"list_available": True})
        assert "Window discovery not available" in result[0].text


class TestHandleTargetWindow:
    @pytest.mark.asyncio
    async def test_no_discovery(self, server_ctx):
        result = await handle_target_window(server_ctx, {"window_title": "Test"})
        assert "Window discovery not available" in result[0].text

    @pytest.mark.asyncio
    async def test_no_title_no_app(self, server_ctx):
        server_ctx.window_discovery = MagicMock()
        result = await handle_target_window(server_ctx, {})
        assert "Provide either" in result[0].text

    @pytest.mark.asyncio
    async def test_window_id_not_found(self, server_ctx):
        server_ctx.window_discovery = MagicMock()
        result = await handle_target_window(server_ctx, {"window_id": "win_99"})
        assert "not found" in result[0].text


class TestHandleCreateWindowGroup:
    @pytest.mark.asyncio
    async def test_create(self, server_ctx):
        result = await handle_create_window_group(server_ctx, {"name": "MyGroup"})
        assert "Window Group Created" in result[0].text
        assert "MyGroup" in result[0].text

    @pytest.mark.asyncio
    async def test_create_with_color(self, server_ctx):
        result = await handle_create_window_group(server_ctx, {"name": "Red", "color": "red"})
        assert "red" in result[0].text


class TestHandleReleaseWindow:
    @pytest.mark.asyncio
    async def test_release_all(self, server_ctx):
        server_ctx.window_manager.add_window_to_active_group(
            app_name="App", window_title="Win", atspi_accessible=MagicMock()
        )
        result = await handle_release_window(server_ctx, {"release_all": True})
        assert "Released 1 windows" in result[0].text

    @pytest.mark.asyncio
    async def test_release_specific(self, server_ctx):
        _, target = server_ctx.window_manager.add_window_to_active_group(
            app_name="App", window_title="Win", atspi_accessible=MagicMock()
        )
        result = await handle_release_window(server_ctx, {"window_id": target.window_id})
        assert "Released window" in result[0].text

    @pytest.mark.asyncio
    async def test_release_not_found(self, server_ctx):
        result = await handle_release_window(server_ctx, {"window_id": "win_99"})
        assert "not found" in result[0].text

    @pytest.mark.asyncio
    async def test_release_no_args(self, server_ctx):
        result = await handle_release_window(server_ctx, {})
        assert "Provide window_id" in result[0].text
