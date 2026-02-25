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
git clone https://github.com/BeckhamLabsLLC/linux-desktop-mcp.git
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

### Example 1: Navigating to a Website in Firefox

```
User: "Open GitHub in Firefox"

Claude uses:
1. desktop_snapshot(app_name="Firefox")
   → Returns UI tree with elements like:
     - ref_5: [entry] "Search or enter address" (editable, focused)
     - ref_12: [button] "Go" (clickable)

2. desktop_click(ref="ref_5", element="URL bar")
   → Clicks to focus the address bar

3. desktop_type(text="https://github.com", ref="ref_5", clear_first=True, submit=True)
   → Types the URL and presses Enter

Result: Firefox navigates to GitHub
```

### Example 2: Saving a File in LibreOffice

```
User: "Save this document as 'report.odt'"

Claude uses:
1. desktop_key(key="s", modifiers=["ctrl"])
   → Opens the Save dialog

2. desktop_snapshot(app_name="LibreOffice")
   → Returns dialog elements including:
     - ref_8: [entry] "File name:" (editable)
     - ref_15: [button] "Save" (clickable)

3. desktop_type(text="report.odt", ref="ref_8", clear_first=True)
   → Types the filename

4. desktop_click(ref="ref_15", element="Save button")
   → Clicks Save

Result: Document saved as report.odt
```

### Example 3: Searching in a Code Editor

```
User: "Search for 'TODO' comments in VS Code"

Claude uses:
1. desktop_find(query="search", app_name="Code")
   → Finds search-related elements

2. desktop_key(key="f", modifiers=["ctrl", "shift"])
   → Opens global search panel

3. desktop_snapshot(app_name="Code")
   → Returns search panel elements:
     - ref_22: [entry] "Search" (editable, focused)
     - ref_25: [checkbox] "Match Case"

4. desktop_type(text="TODO", ref="ref_22", submit=True)
   → Types search query and executes search

Result: VS Code shows all TODO comments across the project
```

### Example 4: Window Targeting for Multi-Window Automation

```
User: "Help me copy data from the spreadsheet to the email"

Claude uses:
1. desktop_context(list_available=True)
   → Lists all available windows

2. desktop_target_window(app_name="LibreOffice Calc", color="green")
   → Targets spreadsheet with green border

3. desktop_target_window(app_name="Thunderbird", color="blue")
   → Targets email client with blue border

4. desktop_snapshot()
   → Only shows elements from targeted windows (reduced context)

5. [Proceeds with copy/paste operations between windows]

Result: Claude can efficiently work across multiple applications
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

## Privacy Policy

See [PRIVACY_POLICY.md](PRIVACY_POLICY.md) for our full privacy policy. In short: Linux Desktop MCP runs entirely on your local machine, collects no data, and requires no network connectivity.

## License

MIT - See [LICENSE](LICENSE) for details.
