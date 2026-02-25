"""MCP Server for Linux Desktop Automation.

Provides Chrome-extension-level semantic element targeting for native Linux
desktop applications using AT-SPI2.
"""

import asyncio
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .atspi_bridge import ATSPI_AVAILABLE, ATSPIBridge
from .detection import detect_capabilities
from .handlers import HANDLER_MAP, ServerContext
from .input_backends import InputManager
from .overlay import OverlayManager
from .tool_definitions import get_tool_definitions
from .window_discovery import ATSPI_AVAILABLE as WINDOW_DISCOVERY_AVAILABLE
from .window_discovery import WindowDiscovery
from .window_manager import WindowGroupManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LinuxDesktopMCPServer:
    """MCP Server for Linux desktop automation."""

    def __init__(self) -> None:
        self._server = Server("linux-desktop-mcp")
        self._ctx = ServerContext()
        self._setup_handlers()

    async def _ensure_initialized(self) -> bool:
        """Ensure the server is initialized."""
        ctx = self._ctx

        if ctx.capabilities is None:
            ctx.capabilities = detect_capabilities()

        if ctx.bridge is None and ATSPI_AVAILABLE:
            try:
                ctx.bridge = ATSPIBridge()
            except Exception as e:
                logger.error(f"Failed to initialize AT-SPI bridge: {e}")

        if ctx.input is None:
            ctx.input = InputManager(ctx.capabilities)

        if ctx.window_manager is None:
            ctx.window_manager = WindowGroupManager()

        if ctx.window_discovery is None and WINDOW_DISCOVERY_AVAILABLE:
            try:
                ctx.window_discovery = WindowDiscovery()
            except Exception as e:
                logger.error(f"Failed to initialize window discovery: {e}")

        if ctx.overlay_manager is None and ctx.capabilities:
            try:
                ctx.overlay_manager = OverlayManager(ctx.capabilities.display_server)
            except Exception as e:
                logger.warning(f"Failed to initialize overlay manager: {e}")

        return ctx.bridge is not None

    def _setup_handlers(self) -> None:
        """Set up MCP tool handlers."""

        @self._server.list_tools()
        async def list_tools() -> list[Tool]:
            return get_tool_definitions()

        @self._server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            try:
                await self._ensure_initialized()

                handler = HANDLER_MAP.get(name)
                if handler is None:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]

                return await handler(self._ctx, arguments)
            except Exception as e:
                logger.exception(f"Error in tool {name}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]

    async def run(self) -> None:
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await self._server.run(
                read_stream, write_stream, self._server.create_initialization_options()
            )


def main() -> None:
    """Entry point for the MCP server."""
    server = LinuxDesktopMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
