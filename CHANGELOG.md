# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
