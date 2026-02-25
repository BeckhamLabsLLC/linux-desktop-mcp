# Privacy Policy

**Linux Desktop MCP** is a local desktop automation tool. This document describes what data it accesses and how it is handled.

## Data Collection

Linux Desktop MCP **does not collect any data**. Specifically:

- No analytics or telemetry
- No usage tracking
- No crash reports sent externally
- No personal information gathered

## Data Access

The server accesses the following local system information during operation:

- **Accessibility tree** (AT-SPI2): UI element names, roles, states, and positions for applications you interact with. This data is read on-demand and not persisted.
- **Environment variables**: Display server type (`WAYLAND_DISPLAY`, `DISPLAY`, `XDG_SESSION_TYPE`) and compositor detection variables, used solely to select the correct input backend.
- **Process information**: `shutil.which` checks for the presence of input tools (`ydotool`, `xdotool`, `wtype`, `scrot`, `grim`).

None of this information is stored, logged, or transmitted.

## Third-Party Services

Linux Desktop MCP **does not communicate with any external services**. It:

- Runs entirely on your local machine
- Requires no network connectivity
- Makes no outbound HTTP requests
- Does not store credentials or tokens

The MCP protocol communication occurs exclusively over local stdio between the MCP client (e.g., Claude Code) and this server.

## Data Storage

No data is written to disk during normal operation. The server holds state (element references, window groups) in memory only, and this state is discarded when the server exits.

## Contact

For privacy-related questions, open an issue on [GitHub](https://github.com/BeckhamLabsLLC/linux-desktop-mcp/issues).
