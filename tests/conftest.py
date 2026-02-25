"""Pytest configuration and shared fixtures."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# ---------------------------------------------------------------------------
# Mock MCP modules before any linux_desktop_mcp imports that need them.
# These are module-level so they take effect at import time.
# ---------------------------------------------------------------------------

_mock_mcp = MagicMock()
_mock_mcp_server = MagicMock()
_mock_mcp_server_stdio = MagicMock()

# Create a proper TextContent mock that returns namespace objects
_mock_mcp_types = MagicMock()


class _FakeTextContent:
    """Lightweight stand-in for mcp.types.TextContent."""

    def __init__(self, *, type: str = "text", text: str = ""):  # noqa: A002
        self.type = type
        self.text = text

    def __repr__(self) -> str:
        return f"TextContent(type={self.type!r}, text={self.text!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, _FakeTextContent):
            return self.type == other.type and self.text == other.text
        return NotImplemented


_mock_mcp_types.TextContent = _FakeTextContent
_mock_mcp_types.Tool = MagicMock
_mock_mcp_types.ToolAnnotations = MagicMock

sys.modules["mcp"] = _mock_mcp
sys.modules["mcp.server"] = _mock_mcp_server
sys.modules["mcp.server.stdio"] = _mock_mcp_server_stdio
sys.modules["mcp.types"] = _mock_mcp_types


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
import pytest  # noqa: E402

from linux_desktop_mcp.detection import DisplayServer, PlatformCapabilities  # noqa: E402
from linux_desktop_mcp.handlers import ServerContext  # noqa: E402
from linux_desktop_mcp.references import (  # noqa: E402
    ElementBounds,
    ElementReference,
    ElementRole,
    ElementState,
    ReferenceManager,
)
from linux_desktop_mcp.window_manager import (  # noqa: E402
    WindowGroupManager,
)

# -- Capability fixtures -----------------------------------------------------


@pytest.fixture
def caps_x11() -> PlatformCapabilities:
    """Capabilities for a typical X11 desktop."""
    return PlatformCapabilities(
        display_server=DisplayServer.X11,
        has_atspi=True,
        atspi_registry_available=True,
        has_xdotool=True,
        has_ydotool=False,
        has_wtype=False,
        has_scrot=True,
        has_grim=False,
        has_tesseract=False,
    )


@pytest.fixture
def caps_wayland() -> PlatformCapabilities:
    """Capabilities for a typical Wayland desktop."""
    return PlatformCapabilities(
        display_server=DisplayServer.WAYLAND,
        has_atspi=True,
        atspi_registry_available=True,
        has_xdotool=False,
        has_ydotool=True,
        has_wtype=True,
        has_scrot=False,
        has_grim=True,
        has_tesseract=False,
        compositor_name="sway",
    )


@pytest.fixture
def caps_no_tools() -> PlatformCapabilities:
    """Capabilities with no input/screenshot tools."""
    return PlatformCapabilities(
        display_server=DisplayServer.X11,
        has_atspi=False,
        atspi_registry_available=False,
        has_xdotool=False,
        has_ydotool=False,
        has_wtype=False,
        has_scrot=False,
        has_grim=False,
        has_tesseract=False,
    )


# -- Mock bridge / input fixtures -------------------------------------------


@pytest.fixture
def mock_bridge() -> MagicMock:
    """Mock ATSPIBridge with a real ReferenceManager."""
    bridge = MagicMock()
    bridge.ref_manager = ReferenceManager()
    return bridge


@pytest.fixture
def mock_input_manager() -> MagicMock:
    """Mock InputManager that reports all abilities available."""
    mgr = MagicMock()
    mgr.can_click = True
    mgr.can_type = True
    mgr.backend_name = "mock"
    return mgr


# -- Reference helpers -------------------------------------------------------


@pytest.fixture
def make_ref():
    """Factory fixture for creating ElementReference objects."""

    def _make(
        ref_id: str = "ref_1",
        name: str = "Test",
        role: ElementRole = ElementRole.BUTTON,
        bounds: ElementBounds | None = None,
        state: ElementState | None = None,
        **kwargs,
    ) -> ElementReference:
        return ElementReference(
            ref_id=ref_id,
            source="atspi",
            role=role,
            name=name,
            bounds=bounds or ElementBounds(x=100, y=100, width=50, height=30),
            state=state or ElementState(),
            **kwargs,
        )

    return _make


# -- ServerContext fixture ---------------------------------------------------


@pytest.fixture
def server_ctx(mock_bridge, mock_input_manager) -> ServerContext:
    """A ServerContext wired with mock bridge, input, and real window manager."""
    return ServerContext(
        capabilities=PlatformCapabilities(
            display_server=DisplayServer.X11,
            has_atspi=True,
            atspi_registry_available=True,
            has_xdotool=True,
        ),
        bridge=mock_bridge,
        input=mock_input_manager,
        window_manager=WindowGroupManager(),
        window_discovery=None,
        overlay_manager=None,
    )
