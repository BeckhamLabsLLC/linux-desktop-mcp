# Linux Desktop MCP Server

[![PyPI version](https://badge.fury.io/py/linux-desktop-mcp.svg)](https://pypi.org/project/linux-desktop-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

> **Built with [Claude Code](https://claude.ai/claude-code)** - This entire MCP server was developed using Claude Code, Anthropic's AI-powered coding assistant. We're proud to showcase what's possible with AI-assisted development!

An MCP server that provides Chrome-extension-level semantic element targeting for native Linux desktop applications using AT-SPI2 (Assistive Technology Service Provider Interface).

## Features

- **Semantic Element References**: Just like Chrome extension's `ref_1`, `ref_2` system
- **Role Detection**: Identifies buttons, text fields, links, menus, etc.
- **State Detection**: Tracks focused, enabled, checked, editable states
- **Natural Language Search**: Find elements by description ("save button", "search field")
- **Cross-Platform Input**: Works on X11, Wayland, and XWayland
- **GTK/Qt/Electron Support**: Works with any application that exposes accessibility

## Installation

### System Dependencies

```bash
# Ubuntu/Debian
sudo apt install python3-pyatspi gir1.2-atspi-2.0 at-spi2-core

# For X11 input simulation
sudo apt install xdotool

# For Wayland input simulation (recommended)
# Install ydotool from source or your package manager
# Then start the daemon:
sudo ydotoold &
```

### Python Package

```bash
# From PyPI
pip install linux-desktop-mcp

# Or from source
git clone https://github.com/yourusername/linux-desktop-mcp.git
cd linux-desktop-mcp
pip install -e .
```

### Enable Accessibility

Ensure accessibility is enabled in your desktop environment:

- **GNOME**: Settings → Accessibility → Enable accessibility features
- **KDE**: System Settings → Accessibility
- Most modern desktops have this enabled by default

## Configuration

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "linux-desktop": {
      "command": "linux-desktop-mcp"
    }
  }
}
```

Or if installed from source:

```json
{
  "mcpServers": {
    "linux-desktop": {
      "command": "python",
      "args": ["-m", "linux_desktop_mcp"]
    }
  }
}
```

## Available Tools

### `desktop_snapshot`

Capture the accessibility tree with semantic element references.

```
Parameters:
  app_name: str (optional) - Filter to specific application
  max_depth: int (default: 15) - Tree traversal depth

Returns:
  Tree of elements with ref_ids:
  - ref_1: [application] Firefox
    - ref_2: [frame] "GitHub - Mozilla Firefox"
      - ref_3: [button] "Back" (clickable)
      - ref_4: [entry] "Search or enter address" (editable, focused)
```

### `desktop_find`

Find elements by natural language query.

```
Parameters:
  query: str - "save button", "search field", "menu containing File"
  app_name: str (optional)

Returns:
  Matching elements with refs, states, and actions
```

### `desktop_click`

Click an element by reference or coordinates.

```
Parameters:
  ref: str - Element reference (e.g., "ref_5")
  element: str - Human description for logging
  coordinate: [x, y] - Fallback if no ref
  button: left|right|middle
  click_type: single|double
  modifiers: [ctrl, shift, alt, super]
```

### `desktop_type`

Type text into an element.

```
Parameters:
  text: str - Text to type
  ref: str - Element to focus first (optional)
  element: str - Human description
  clear_first: bool - Ctrl+A, Delete before typing
  submit: bool - Press Enter after
```

### `desktop_key`

Press keyboard keys/shortcuts.

```
Parameters:
  key: str - Key name (Return, Tab, Escape, a, etc.)
  modifiers: [ctrl, shift, alt, super]
```

### `desktop_capabilities`

Check available automation capabilities.

## Example Usage

```
# 1. Take a snapshot to see available elements
desktop_snapshot(app_name="Firefox")

# 2. Find a specific element
desktop_find(query="search bar")

# 3. Click the element
desktop_click(ref="ref_5", element="URL bar")

# 4. Type into it
desktop_type(text="https://github.com", ref="ref_5", submit=True)

# 5. Use keyboard shortcuts
desktop_key(key="t", modifiers=["ctrl"])  # New tab
```

## Platform Support

| Feature | X11 | Wayland | XWayland |
|---------|-----|---------|----------|
| AT-SPI discovery | Full | Full | Full |
| Click by ref | Full | Full | Full |
| Type text | Full | Full | Full |
| ydotool input | Full | Full | Full |
| xdotool input | Full | No | Yes |

## Troubleshooting

### "AT-SPI2 not available"

```bash
sudo apt install python3-pyatspi gir1.2-atspi-2.0 at-spi2-core
```

### "AT-SPI2 registry not running"

Ensure accessibility is enabled in your desktop settings. You may need to log out and back in.

### "No input backend available" (Wayland)

```bash
# Install and start ydotool daemon
sudo ydotoold &
```

### Elements not showing up

Some applications may not expose accessibility information. Modern GTK3/4, Qt5/6, and Electron apps generally work well.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     MCP Protocol Layer                       │
│              (JSON-RPC over stdio, tool defs)                │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                  Reference Manager                           │
│          (ref_1, ref_2 mapping, lifecycle, GC)              │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┴───────────────────┐
          │                                       │
┌─────────────────────┐             ┌─────────────────────────┐
│   AT-SPI2 Backend   │             │   Input Backends        │
│     (pyatspi)       │             │ (ydotool/xdotool/wtype) │
└─────────────────────┘             └─────────────────────────┘
```

## Contributing

This project was created with Claude Code and we warmly welcome contributions! Whether you want to:

- Report bugs or request features
- Submit pull requests
- Fork and build your own version
- Improve documentation

We're very open to help and collaboration. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT - See [LICENSE](LICENSE) for details.
