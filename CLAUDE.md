# CLAUDE.md

Project guide for AI-assisted development of linux-desktop-mcp.

## Project Overview

An MCP server providing Chrome-extension-level semantic element targeting for native Linux desktop applications using AT-SPI2. Exposes 11 tools for desktop automation (snapshot, find, click, type, key, capabilities, context, target_window, create_window_group, release_window).

## Layout

```
src/linux_desktop_mcp/
  __init__.py          # Package entry, version, exception exports
  server.py            # MCP server setup, initialization, tool dispatch
  handlers.py          # ServerContext dataclass + 10 async handler functions
  tool_definitions.py  # get_tool_definitions() with all 11 Tool schemas
  exceptions.py        # Custom exception hierarchy (LinuxDesktopMCPError base)
  atspi_bridge.py      # AT-SPI2 tree building, element interaction (ThreadPoolExecutor)
  references.py        # ElementReference, ReferenceManager, GC
  input_backends.py    # InputManager + YdotoolBackend, XdotoolBackend, WtypeBackend
  window_manager.py    # WindowGroup, WindowTarget, WindowGroupManager
  window_discovery.py  # Window enumeration via AT-SPI desktop
  overlay.py           # GTK3 border overlay windows (X11 backend)
  detection.py         # Display server, compositor, and tool detection
tests/
  conftest.py          # MCP module mocks, shared fixtures
  test_server.py       # Handler tests via ServerContext
  test_window_manager.py
  test_detection.py
  test_input_backends_manager.py
  test_window_discovery.py
  test_overlay.py
```

## Build & Test

```bash
# Run tests (mocks MCP + AT-SPI, no desktop needed)
PYTHONPATH=src pytest tests/ -v

# Lint and format
ruff check .
ruff format .

# Import check
python -c "from linux_desktop_mcp import __version__; print(__version__)"
```

## Code Conventions

- **Python 3.10+** target. Use `X | None` union syntax, `dict[str, Any]` (not `Dict`).
- **Exception handling**: Use custom exceptions from `exceptions.py`. AT-SPI modules use `_GLibError` conditional import pattern. Never use bare `except Exception` except in the top-level `call_tool` safety net.
- **Async handlers**: Each tool handler is a standalone async function in `handlers.py` receiving `(ctx: ServerContext, args: dict)` and returning `list[TextContent]`.
- **Input backends**: Subprocess-based, mock `asyncio.create_subprocess_exec` in tests.
- **AT-SPI bridge**: Runs blocking AT-SPI calls in `ThreadPoolExecutor` via `asyncio.to_thread`. Uses `threading.Lock` for thread safety.
- **Tests**: Pure Python where possible (dataclasses, enums). MCP modules mocked at conftest level. No real desktop or AT-SPI required.
- **Formatting**: ruff with line-length=100, double quotes, isort-compatible imports.
