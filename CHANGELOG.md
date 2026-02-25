# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-02-25

### Added
- Custom exception hierarchy (`LinuxDesktopMCPError` base) with 13 specific exception classes for AT-SPI, input, overlay, window, and reference errors
- 185+ new tests across 7 test files (total: ~230 tests), covering window manager, detection, input backends, handlers, window discovery, and overlay
- `PRIVACY_POLICY.md` standalone privacy document
- `CLAUDE.md` project guide for AI-assisted development
- `[project.urls]` in pyproject.toml (Repository, Documentation, Issues, Changelog)
- `Typing :: Typed` classifier

### Changed
- Refactored `server.py` (962 lines) into 3 focused modules: `server.py` (~100 lines), `handlers.py` (~620 lines), `tool_definitions.py` (~250 lines)
- `ServerContext` dataclass replaces monolithic server class for handler state
- `HANDLER_MAP` dispatcher dict replaces if/elif chain in `call_tool`
- Narrowed ~45 bare `except Exception` catches to specific types (`_GLibError`, `FileNotFoundError`, `OSError`, custom exceptions)
- Replaced `Dict` with `dict` and added `-> None`, `-> Any`, `-> dict[str, Any]` return types across all modules
- Development status classifier updated from Alpha to Beta
- Version bumped to 0.2.0

### Fixed
- Bug in `WindowGroupManager.delete_group` where empty `WindowGroup` was treated as falsy due to `__len__` returning 0, preventing active group ID updates
- Fixed `yourusername` placeholder URLs in README.md and CONTRIBUTING.md

## [0.1.0] - 2025-01-07

### Added
- Initial release of Linux Desktop MCP
- 11 MCP tools for desktop automation:
  - `desktop_snapshot` - Capture accessibility tree with semantic refs
  - `desktop_find` - Find elements by natural language query
  - `desktop_click` - Click elements by ref or coordinates
  - `desktop_type` - Type text into elements
  - `desktop_key` - Press keyboard keys/shortcuts
  - `desktop_capabilities` - Check available automation capabilities
  - `desktop_context` - Get window group context
  - `desktop_target_window` - Target specific windows with colored borders
  - `desktop_create_window_group` - Create window groups
  - `desktop_release_window` - Release windows from tracking
- AT-SPI2 accessibility tree support for semantic element targeting
- Reference system (`ref_1`, `ref_2`, etc.) similar to Chrome extension
- Input backends:
  - ydotool (Wayland + X11)
  - xdotool (X11 only)
  - wtype (Wayland keyboard only)
- Window grouping with visual border overlays
- X11, Wayland, and XWayland support
- Automatic garbage collection for stale references
- Input validation for security
- Comprehensive documentation and examples

### Security
- Added input validation for coordinates (0-65535 range)
- Added text length limits (10,000 characters max)
- Added query length limits (1,000 characters max)
- Safe subprocess execution for input tools
