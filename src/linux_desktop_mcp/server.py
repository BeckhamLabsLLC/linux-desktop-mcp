"""MCP Server for Linux Desktop Automation.

Provides Chrome-extension-level semantic element targeting for native Linux
desktop applications using AT-SPI2.
"""

import asyncio
import logging
from typing import Any, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .atspi_bridge import ATSPI_AVAILABLE, ATSPIBridge
from .detection import PlatformCapabilities, detect_capabilities
from .input_backends import InputManager
from .overlay import OverlayManager
from .references import ElementReference
from .window_discovery import ATSPI_AVAILABLE as WINDOW_DISCOVERY_AVAILABLE
from .window_discovery import WindowDiscovery
from .window_manager import GroupColor, WindowGeometry, WindowGroupManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Input validation constants
MAX_TEXT_LENGTH = 10000
MAX_QUERY_LENGTH = 1000
MAX_COORDINATE = 65535
MIN_COORDINATE = 0


class LinuxDesktopMCPServer:
    """MCP Server for Linux desktop automation."""

    def __init__(self):
        self._server = Server("linux-desktop-mcp")
        self._capabilities: Optional[PlatformCapabilities] = None
        self._bridge: Optional[ATSPIBridge] = None
        self._input: Optional[InputManager] = None
        self._window_manager: Optional[WindowGroupManager] = None
        self._window_discovery: Optional[WindowDiscovery] = None
        self._overlay_manager = None  # Will be set when overlay.py is created
        self._setup_handlers()

    def _validate_coordinate(self, value: int) -> bool:
        """Validate a coordinate value is within bounds."""
        return MIN_COORDINATE <= value <= MAX_COORDINATE

    def _validate_coordinates(self, x: int, y: int) -> tuple[bool, str]:
        """Validate x,y coordinates. Returns (is_valid, error_message)."""
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return False, "Coordinates must be numbers"
        x, y = int(x), int(y)
        if not self._validate_coordinate(x):
            return False, f"X coordinate {x} out of range (0-{MAX_COORDINATE})"
        if not self._validate_coordinate(y):
            return False, f"Y coordinate {y} out of range (0-{MAX_COORDINATE})"
        return True, ""

    def _validate_string(self, value: str, max_len: int, name: str = "value") -> tuple[bool, str]:
        """Validate a string value. Returns (is_valid, error_message)."""
        if not isinstance(value, str):
            return False, f"{name} must be a string"
        if len(value) > max_len:
            return False, f"{name} too long ({len(value)} > {max_len})"
        return True, ""

    def _setup_handlers(self):
        """Set up MCP tool handlers."""

        @self._server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="desktop_snapshot",
                    description="Capture accessibility tree with semantic element references. "
                    "Returns a tree of UI elements with ref IDs that can be used for interaction.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "app_name": {
                                "type": "string",
                                "description": "Filter to specific application name (optional)",
                            },
                            "max_depth": {
                                "type": "integer",
                                "description": "Maximum tree traversal depth (default: 15)",
                                "default": 15,
                            },
                        },
                    },
                ),
                Tool(
                    name="desktop_find",
                    description="Find elements by natural language query. "
                    "Search for buttons, text fields, links, etc. by name or role.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Natural language query (e.g., 'save button', 'search field')",
                            },
                            "app_name": {
                                "type": "string",
                                "description": "Filter to specific application (optional)",
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="desktop_click",
                    description="Click on an element by reference or coordinates.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "ref": {
                                "type": "string",
                                "description": "Element reference ID (e.g., 'ref_5')",
                            },
                            "element": {
                                "type": "string",
                                "description": "Human-readable element description for logging",
                            },
                            "coordinate": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "minItems": 2,
                                "maxItems": 2,
                                "description": "Fallback [x, y] coordinates if no ref",
                            },
                            "button": {
                                "type": "string",
                                "enum": ["left", "right", "middle"],
                                "default": "left",
                            },
                            "click_type": {
                                "type": "string",
                                "enum": ["single", "double"],
                                "default": "single",
                            },
                            "modifiers": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Modifier keys like ['ctrl', 'shift']",
                            },
                        },
                    },
                ),
                Tool(
                    name="desktop_type",
                    description="Type text into an element. Clicks to focus first if ref provided.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "Text to type"},
                            "ref": {
                                "type": "string",
                                "description": "Element reference to type into (optional)",
                            },
                            "element": {
                                "type": "string",
                                "description": "Human-readable element description",
                            },
                            "clear_first": {
                                "type": "boolean",
                                "description": "Clear existing text before typing (Ctrl+A, Delete)",
                                "default": False,
                            },
                            "submit": {
                                "type": "boolean",
                                "description": "Press Enter after typing",
                                "default": False,
                            },
                        },
                        "required": ["text"],
                    },
                ),
                Tool(
                    name="desktop_key",
                    description="Press a keyboard key or shortcut.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "key": {
                                "type": "string",
                                "description": "Key name (e.g., 'Return', 'Tab', 'Escape', 'a')",
                            },
                            "modifiers": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Modifier keys like ['ctrl', 'shift', 'alt', 'super']",
                            },
                        },
                        "required": ["key"],
                    },
                ),
                Tool(
                    name="desktop_capabilities",
                    description="Get information about available desktop automation capabilities.",
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="desktop_context",
                    description="Get information about the current window group context and available windows. "
                    "Similar to Chrome extension's tabs_context. Call this to understand which windows "
                    "Claude is currently working with.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "list_available": {
                                "type": "boolean",
                                "description": "Also list all available windows on desktop (default: false)",
                                "default": False,
                            }
                        },
                    },
                ),
                Tool(
                    name="desktop_target_window",
                    description="Target a specific window for automation. Draws a colored border around "
                    "the window to indicate it's being controlled by Claude. The targeted window "
                    "will be added to the current window group. Use desktop_context first to see "
                    "available windows.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "window_title": {
                                "type": "string",
                                "description": "Window title to match (partial match supported)",
                            },
                            "app_name": {
                                "type": "string",
                                "description": "Application name to filter by",
                            },
                            "window_id": {
                                "type": "string",
                                "description": "Direct window ID from desktop_context (win_N)",
                            },
                            "color": {
                                "type": "string",
                                "enum": ["blue", "purple", "green", "orange", "red", "cyan"],
                                "description": "Border color for the window (default: blue)",
                                "default": "blue",
                            },
                        },
                    },
                ),
                Tool(
                    name="desktop_create_window_group",
                    description="Create a new window group for organizing targeted windows. "
                    "Similar to Chrome's tab groups. If a window group already exists, "
                    "this creates a new one and makes it active.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Optional name for the group",
                            },
                            "color": {
                                "type": "string",
                                "enum": ["blue", "purple", "green", "orange", "red", "cyan"],
                                "description": "Color for the group (default: blue)",
                                "default": "blue",
                            },
                        },
                    },
                ),
                Tool(
                    name="desktop_release_window",
                    description="Release a window from the current group. Removes the border overlay "
                    "and stops tracking the window.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "window_id": {
                                "type": "string",
                                "description": "Window ID to release (win_N from desktop_context)",
                            },
                            "release_all": {
                                "type": "boolean",
                                "description": "Release all windows in current group",
                                "default": False,
                            },
                        },
                    },
                ),
            ]

        @self._server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            try:
                if name == "desktop_snapshot":
                    return await self._handle_snapshot(arguments)
                elif name == "desktop_find":
                    return await self._handle_find(arguments)
                elif name == "desktop_click":
                    return await self._handle_click(arguments)
                elif name == "desktop_type":
                    return await self._handle_type(arguments)
                elif name == "desktop_key":
                    return await self._handle_key(arguments)
                elif name == "desktop_capabilities":
                    return await self._handle_capabilities(arguments)
                elif name == "desktop_context":
                    return await self._handle_context(arguments)
                elif name == "desktop_target_window":
                    return await self._handle_target_window(arguments)
                elif name == "desktop_create_window_group":
                    return await self._handle_create_window_group(arguments)
                elif name == "desktop_release_window":
                    return await self._handle_release_window(arguments)
                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]
            except Exception as e:
                logger.exception(f"Error in tool {name}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]

    async def _ensure_initialized(self) -> bool:
        """Ensure the server is initialized."""
        if self._capabilities is None:
            self._capabilities = detect_capabilities()

        if self._bridge is None and ATSPI_AVAILABLE:
            try:
                self._bridge = ATSPIBridge()
            except Exception as e:
                logger.error(f"Failed to initialize AT-SPI bridge: {e}")

        if self._input is None:
            self._input = InputManager(self._capabilities)

        if self._window_manager is None:
            self._window_manager = WindowGroupManager()

        if self._window_discovery is None and WINDOW_DISCOVERY_AVAILABLE:
            try:
                self._window_discovery = WindowDiscovery()
            except Exception as e:
                logger.error(f"Failed to initialize window discovery: {e}")

        if self._overlay_manager is None and self._capabilities:
            try:
                self._overlay_manager = OverlayManager(self._capabilities.display_server)
            except Exception as e:
                logger.warning(f"Failed to initialize overlay manager: {e}")

        return self._bridge is not None

    async def _handle_snapshot(self, args: dict[str, Any]) -> list[TextContent]:
        """Handle desktop_snapshot tool."""
        if not await self._ensure_initialized():
            return [
                TextContent(
                    type="text",
                    text="Error: AT-SPI2 not available. Install: sudo apt install python3-pyatspi gir1.2-atspi-2.0 at-spi2-core",
                )
            ]

        app_name = args.get("app_name")
        max_depth = args.get("max_depth", 15)

        # Check if we have targeted windows - if so, only scan those
        group = self._window_manager.get_active_group() if self._window_manager else None
        targeted_mode = False

        if group and group.windows and not app_name:
            # Use targeted windows for reduced context
            targeted_mode = True
            # Validate windows first (remove closed ones)
            group.validate_windows()

            if not group.windows:
                return [
                    TextContent(
                        type="text",
                        text="All targeted windows have been closed. Use desktop_target_window to target new windows.",
                    )
                ]

            # Get active window or all windows in group
            active_window = group.get_active_window()
            if active_window and active_window.atspi_accessible:
                refs = await self._bridge.build_tree_for_window(
                    active_window.atspi_accessible, max_depth=max_depth
                )
                window_info = f'Window: "{active_window.window_title}" ({active_window.app_name})'
            else:
                # Build tree for all windows in group
                window_accessibles = [
                    t.atspi_accessible for t in group.windows.values() if t.atspi_accessible
                ]
                refs = await self._bridge.build_tree_for_windows(
                    window_accessibles, max_depth=max_depth
                )
                window_info = f"All {len(group.windows)} targeted windows"
        else:
            # No targeting - use full desktop scan (original behavior)
            refs = await self._bridge.build_tree(app_name_filter=app_name, max_depth=max_depth)
            window_info = None

        if not refs:
            return [
                TextContent(
                    type="text",
                    text="No elements found. Ensure applications are running and accessibility is enabled.",
                )
            ]

        if targeted_mode:
            output_lines = ["# Accessibility Tree (Targeted)", f"# {window_info}", ""]
        else:
            output_lines = ["# Desktop Accessibility Tree", ""]
            if app_name:
                output_lines.insert(1, f"# Filtered by app: {app_name}")

        def build_tree_output(ref: ElementReference, indent: int = 0) -> list[str]:
            lines = [ref.format_for_display(indent)]
            for child_id in ref.child_refs:
                child = self._bridge.ref_manager.get(child_id)
                if child:
                    lines.extend(build_tree_output(child, indent + 1))
            return lines

        root_refs = [r for r in refs if r.parent_ref is None]
        for root in root_refs:
            output_lines.extend(build_tree_output(root))
            output_lines.append("")

        output_lines.append(f"\nTotal elements: {len(refs)}")
        if targeted_mode:
            output_lines.append("(Context reduced via window targeting)")

        return [TextContent(type="text", text="\n".join(output_lines))]

    async def _handle_find(self, args: dict[str, Any]) -> list[TextContent]:
        """Handle desktop_find tool."""
        if not await self._ensure_initialized():
            return [TextContent(type="text", text="Error: AT-SPI2 not available")]

        query = args.get("query", "")
        app_name = args.get("app_name")

        # Validate query
        valid, error = self._validate_string(query, MAX_QUERY_LENGTH, "query")
        if not valid:
            return [TextContent(type="text", text=f"Error: {error}")]
        if not query.strip():
            return [TextContent(type="text", text="Error: Query cannot be empty")]

        # Check if we have targeted windows - if so, only search those
        group = self._window_manager.get_active_group() if self._window_manager else None
        targeted_mode = False

        if group and group.windows and not app_name:
            # Use targeted windows for reduced context
            targeted_mode = True
            group.validate_windows()

            if not group.windows:
                return [
                    TextContent(
                        type="text",
                        text="All targeted windows have been closed. Use desktop_target_window to target new windows.",
                    )
                ]

            # Get active window or all windows in group
            active_window = group.get_active_window()
            if active_window and active_window.atspi_accessible:
                await self._bridge.build_tree_for_window(active_window.atspi_accessible)
            else:
                window_accessibles = [
                    t.atspi_accessible for t in group.windows.values() if t.atspi_accessible
                ]
                await self._bridge.build_tree_for_windows(window_accessibles)
        else:
            await self._bridge.build_tree(app_name_filter=app_name)

        matches = self._bridge.ref_manager.find_by_query(query)

        if not matches:
            scope_note = " (in targeted windows)" if targeted_mode else ""
            return [
                TextContent(type="text", text=f"No elements found matching: {query}{scope_note}")
            ]

        scope_note = " (in targeted windows)" if targeted_mode else ""
        output_lines = [f"# Found {len(matches)} elements matching '{query}'{scope_note}", ""]

        for ref in matches[:20]:
            state_str = ", ".join(ref.state.to_list()) if ref.state.to_list() else "normal"
            bounds = f"({ref.bounds.x}, {ref.bounds.y}, {ref.bounds.width}x{ref.bounds.height})"
            output_lines.append(
                f'- {ref.ref_id}: [{ref.role.value}] "{ref.name}" ({state_str}) at {bounds}'
            )
            if ref.app_name:
                output_lines.append(f"  App: {ref.app_name}")
            if ref.available_actions:
                output_lines.append(f"  Actions: {', '.join(ref.available_actions)}")
            output_lines.append("")

        if len(matches) > 20:
            output_lines.append(f"... and {len(matches) - 20} more")

        return [TextContent(type="text", text="\n".join(output_lines))]

    async def _handle_click(self, args: dict[str, Any]) -> list[TextContent]:
        """Handle desktop_click tool."""
        if not await self._ensure_initialized():
            return [TextContent(type="text", text="Error: AT-SPI2 not available")]

        ref_id = args.get("ref")
        coordinate = args.get("coordinate")
        button = args.get("button", "left")
        click_type = args.get("click_type", "single")
        modifiers = args.get("modifiers")
        element_desc = args.get("element", "element")

        if ref_id:
            ref = self._bridge.ref_manager.get(ref_id)
            if not ref:
                return [
                    TextContent(
                        type="text",
                        text=f"Error: Reference {ref_id} not found or expired. Run desktop_snapshot first.",
                    )
                ]

            if ref.atspi_accessible and "click" in ref.available_actions:
                success = await self._bridge.click_element(ref, button)
                if success:
                    return [
                        TextContent(
                            type="text", text=f"Clicked {element_desc} ({ref_id}) via AT-SPI action"
                        )
                    ]

            if self._input and self._input.can_click:
                success = await self._input.click_element(ref, button, click_type, modifiers)
                if success:
                    x, y = ref.bounds.center
                    return [
                        TextContent(
                            type="text", text=f"Clicked {element_desc} ({ref_id}) at ({x}, {y})"
                        )
                    ]

            return [TextContent(type="text", text=f"Failed to click {element_desc}")]

        elif coordinate:
            if not self._input or not self._input.can_click:
                return [TextContent(type="text", text="Error: No input backend available")]

            if len(coordinate) != 2:
                return [TextContent(type="text", text="Error: Coordinate must be [x, y]")]

            x, y = coordinate
            valid, error = self._validate_coordinates(x, y)
            if not valid:
                return [TextContent(type="text", text=f"Error: {error}")]

            x, y = int(x), int(y)
            success = await self._input.click(x, y, button, click_type, modifiers)
            if success:
                return [TextContent(type="text", text=f"Clicked at ({x}, {y})")]
            return [TextContent(type="text", text=f"Failed to click at ({x}, {y})")]

        return [TextContent(type="text", text="Error: Provide either ref or coordinate")]

    async def _handle_type(self, args: dict[str, Any]) -> list[TextContent]:
        """Handle desktop_type tool."""
        if not await self._ensure_initialized():
            return [TextContent(type="text", text="Error: Not initialized")]

        if not self._input or not self._input.can_type:
            return [TextContent(type="text", text="Error: No keyboard input available")]

        text = args.get("text", "")
        ref_id = args.get("ref")

        # Validate text length
        valid, error = self._validate_string(text, MAX_TEXT_LENGTH, "text")
        if not valid:
            return [TextContent(type="text", text=f"Error: {error}")]
        clear_first = args.get("clear_first", False)
        submit = args.get("submit", False)
        element_desc = args.get("element", "element")

        if ref_id:
            ref = self._bridge.ref_manager.get(ref_id)
            if not ref:
                return [
                    TextContent(type="text", text=f"Error: Reference {ref_id} not found or expired")
                ]

            if ref.atspi_accessible and ref.state.editable:
                success = await self._bridge.set_text(ref, text, clear_first)
                if success:
                    msg = f"Set text in {element_desc} ({ref_id}) via AT-SPI"
                    if submit:
                        await self._input.key("Return")
                        msg += " and pressed Enter"
                    return [TextContent(type="text", text=msg)]

            if self._input.can_click:
                success = await self._input.click_element(ref)
                if not success:
                    return [TextContent(type="text", text=f"Failed to focus {element_desc}")]
                await asyncio.sleep(0.1)

        if clear_first:
            await self._input.key("a", ["ctrl"])
            await asyncio.sleep(0.05)
            await self._input.key("Delete")
            await asyncio.sleep(0.05)

        success = await self._input.type_text(text)
        if not success:
            return [TextContent(type="text", text="Failed to type text")]

        msg = "Typed text"
        if ref_id:
            msg = f"Typed text in {element_desc} ({ref_id})"

        if submit:
            await asyncio.sleep(0.05)
            await self._input.key("Return")
            msg += " and pressed Enter"

        return [TextContent(type="text", text=msg)]

    async def _handle_key(self, args: dict[str, Any]) -> list[TextContent]:
        """Handle desktop_key tool."""
        if not await self._ensure_initialized():
            return [TextContent(type="text", text="Error: Not initialized")]

        if not self._input or not self._input.can_type:
            return [TextContent(type="text", text="Error: No keyboard input available")]

        key = args.get("key", "")
        modifiers = args.get("modifiers")

        # Validate key name
        if not key or not isinstance(key, str):
            return [TextContent(type="text", text="Error: Key name is required")]
        if len(key) > 50:
            return [TextContent(type="text", text="Error: Key name too long")]

        success = await self._input.key(key, modifiers)
        if success:
            mod_str = "+".join(modifiers) + "+" if modifiers else ""
            return [TextContent(type="text", text=f"Pressed {mod_str}{key}")]

        return [TextContent(type="text", text="Failed to press key")]

    async def _handle_capabilities(self, args: dict[str, Any]) -> list[TextContent]:
        """Handle desktop_capabilities tool."""
        await self._ensure_initialized()

        caps = self._capabilities
        lines = [
            "# Linux Desktop Automation Capabilities",
            "",
            f"Display Server: {caps.display_server.value}",
        ]
        if caps.compositor_name:
            lines.append(f"Compositor: {caps.compositor_name}")
        lines.extend(
            [
                f"AT-SPI2 Available: {caps.has_atspi}",
                f"AT-SPI2 Registry Running: {caps.atspi_registry_available}",
                "",
                "## Input Tools",
                f"- ydotool: {'Available' if caps.has_ydotool else 'Not found'}",
                f"- xdotool: {'Available' if caps.has_xdotool else 'Not found'}",
                f"- wtype: {'Available' if caps.has_wtype else 'Not found'}",
                "",
                f"Active Input Backend: {self._input.backend_name if self._input else 'None'}",
                f"Can Click: {self._input.can_click if self._input else False}",
                f"Can Type: {self._input.can_type if self._input else False}",
                "",
                "## Screenshot Tools",
                f"- scrot: {'Available' if caps.has_scrot else 'Not found'}",
                f"- grim: {'Available' if caps.has_grim else 'Not found'}",
                "",
                "## OCR Tools",
                f"- tesseract: {'Available' if caps.has_tesseract else 'Not found'}",
                "",
                "## Window Targeting",
                f"- Window Discovery: {'Available' if self._window_discovery else 'Not available'}",
            ]
        )
        if self._overlay_manager:
            lines.append(
                f"- Visual Overlays: {'Available' if self._overlay_manager.has_visual_support else 'Not supported'}"
            )
            if caps.display_server.value == "wayland" and caps.compositor_name == "gnome":
                lines.append("  (GNOME Wayland does not support window overlays)")
        else:
            lines.append("- Visual Overlays: Not initialized")
        if caps.has_layer_shell:
            lines.append("- Layer Shell: Available")

        if caps.errors:
            lines.append("")
            lines.append("## Errors/Warnings")
            for error in caps.errors:
                lines.append(f"- {error}")

        return [TextContent(type="text", text="\n".join(lines))]

    async def _handle_context(self, args: dict[str, Any]) -> list[TextContent]:
        """Handle desktop_context tool - get window group context."""
        if not await self._ensure_initialized():
            return [TextContent(type="text", text="Error: Not initialized")]

        list_available = args.get("list_available", False)
        output_lines = ["# Desktop Context", ""]

        # Show current window group info
        group = self._window_manager.get_active_group()
        if group:
            output_lines.append("## Active Window Group")
            output_lines.append(f"- Group ID: {group.group_id}")
            if group.name:
                output_lines.append(f"- Name: {group.name}")
            output_lines.append(f"- Color: {group.color.name.lower()} ({group.color.value})")
            output_lines.append(f"- Windows: {len(group.windows)}")
            output_lines.append("")

            if group.windows:
                output_lines.append("### Targeted Windows")
                # Validate windows first (remove closed ones)
                removed = group.validate_windows()
                if removed:
                    output_lines.append(f"(Removed {len(removed)} closed windows)")

                for target in group.windows.values():
                    active_marker = " [ACTIVE]" if target.is_active else ""
                    geom_str = ""
                    if target.geometry:
                        geom_str = f" at ({target.geometry.x}, {target.geometry.y}, {target.geometry.width}x{target.geometry.height})"
                    output_lines.append(
                        f'- {target.window_id}: "{target.window_title}" ({target.app_name}){geom_str}{active_marker}'
                    )
                output_lines.append("")
        else:
            output_lines.append(
                "No active window group. Use desktop_target_window to target a window."
            )
            output_lines.append("")

        # List available windows if requested
        if list_available:
            output_lines.append("## Available Windows")
            if self._window_discovery:
                try:
                    windows = await self._window_discovery.enumerate_windows()
                    if windows:
                        for i, win in enumerate(windows):
                            active_marker = " [FOCUSED]" if win.is_focused else ""
                            geom_str = ""
                            if win.geometry:
                                geom_str = f" at ({win.geometry.x}, {win.geometry.y}, {win.geometry.width}x{win.geometry.height})"
                            output_lines.append(
                                f'- "{win.window_title}" ({win.app_name}){geom_str}{active_marker}'
                            )
                    else:
                        output_lines.append("No windows found")
                except Exception as e:
                    output_lines.append(f"Error enumerating windows: {e}")
            else:
                output_lines.append("Window discovery not available")

        return [TextContent(type="text", text="\n".join(output_lines))]

    async def _handle_target_window(self, args: dict[str, Any]) -> list[TextContent]:
        """Handle desktop_target_window tool - target a window for automation."""
        if not await self._ensure_initialized():
            return [TextContent(type="text", text="Error: Not initialized")]

        if not self._window_discovery:
            return [TextContent(type="text", text="Error: Window discovery not available")]

        window_title = args.get("window_title")
        app_name = args.get("app_name")
        window_id = args.get("window_id")
        color_str = args.get("color", "blue")
        color = GroupColor.from_string(color_str)

        # If window_id provided, find in existing targeted windows
        if window_id:
            result = self._window_manager.find_window_by_id(window_id)
            if result:
                group, target = result
                group.set_active_window(window_id)
                return [
                    TextContent(
                        type="text", text=f"Switched to window: {target.window_title} ({window_id})"
                    )
                ]
            else:
                return [
                    TextContent(
                        type="text", text=f"Window ID {window_id} not found in targeted windows"
                    )
                ]

        # Find window by title/app name
        if not window_title and not app_name:
            return [
                TextContent(
                    type="text", text="Error: Provide either window_title, app_name, or window_id"
                )
            ]

        try:
            if window_title:
                windows = await self._window_discovery.find_window_by_title(window_title, app_name)
            else:
                windows = await self._window_discovery.find_windows_by_app(app_name)

            if not windows:
                search_desc = f"title='{window_title}'" if window_title else f"app='{app_name}'"
                return [TextContent(type="text", text=f"No windows found matching {search_desc}")]

            # Use first match
            win = windows[0]
            geometry = (
                WindowGeometry(
                    x=win.geometry.x,
                    y=win.geometry.y,
                    width=win.geometry.width,
                    height=win.geometry.height,
                )
                if win.geometry
                else None
            )

            group, target = self._window_manager.add_window_to_active_group(
                app_name=win.app_name,
                window_title=win.window_title,
                atspi_accessible=win.atspi_accessible,
                geometry=geometry,
                color=color,
            )

            # Show border overlay (if overlay manager available)
            if self._overlay_manager and geometry:
                try:
                    self._overlay_manager.show_border(target.window_id, geometry, color)
                except Exception as e:
                    logger.warning(f"Failed to show border overlay: {e}")

            output_lines = [
                "# Window Targeted",
                "",
                f"- Window ID: {target.window_id}",
                f'- Title: "{target.window_title}"',
                f"- Application: {target.app_name}",
                f"- Group: {group.group_id}",
                f"- Color: {color.name.lower()}",
            ]
            if geometry:
                output_lines.append(f"- Position: ({geometry.x}, {geometry.y})")
                output_lines.append(f"- Size: {geometry.width}x{geometry.height}")

            if len(windows) > 1:
                output_lines.append("")
                output_lines.append(f"Note: {len(windows)} windows matched. Targeted first match.")

            return [TextContent(type="text", text="\n".join(output_lines))]

        except Exception as e:
            return [TextContent(type="text", text=f"Error targeting window: {e}")]

    async def _handle_create_window_group(self, args: dict[str, Any]) -> list[TextContent]:
        """Handle desktop_create_window_group tool."""
        if not await self._ensure_initialized():
            return [TextContent(type="text", text="Error: Not initialized")]

        name = args.get("name")
        color_str = args.get("color", "blue")
        color = GroupColor.from_string(color_str)

        group = self._window_manager.create_group(name=name, color=color)
        self._window_manager.set_active_group(group.group_id)

        output_lines = [
            "# Window Group Created",
            "",
            f"- Group ID: {group.group_id}",
        ]
        if name:
            output_lines.append(f"- Name: {name}")
        output_lines.append(f"- Color: {color.name.lower()} ({color.value})")
        output_lines.append("")
        output_lines.append("Use desktop_target_window to add windows to this group.")

        return [TextContent(type="text", text="\n".join(output_lines))]

    async def _handle_release_window(self, args: dict[str, Any]) -> list[TextContent]:
        """Handle desktop_release_window tool."""
        if not await self._ensure_initialized():
            return [TextContent(type="text", text="Error: Not initialized")]

        window_id = args.get("window_id")
        release_all = args.get("release_all", False)

        if release_all:
            count = self._window_manager.release_all_windows()
            # Hide all overlays
            if self._overlay_manager:
                try:
                    self._overlay_manager.hide_all_borders()
                except Exception as e:
                    logger.warning(f"Failed to hide overlays: {e}")
            return [TextContent(type="text", text=f"Released {count} windows from all groups")]

        if not window_id:
            return [
                TextContent(type="text", text="Error: Provide window_id or set release_all=true")
            ]

        target = self._window_manager.release_window(window_id)
        if target:
            # Hide overlay for this window
            if self._overlay_manager:
                try:
                    self._overlay_manager.hide_border(window_id)
                except Exception as e:
                    logger.warning(f"Failed to hide overlay: {e}")
            return [
                TextContent(
                    type="text", text=f'Released window: "{target.window_title}" ({window_id})'
                )
            ]
        else:
            return [TextContent(type="text", text=f"Window ID {window_id} not found")]

    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await self._server.run(
                read_stream, write_stream, self._server.create_initialization_options()
            )


def main():
    """Entry point for the MCP server."""
    server = LinuxDesktopMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
