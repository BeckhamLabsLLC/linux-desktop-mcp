"""Linux Desktop Automation MCP Server.

Provides Chrome-extension-level semantic element targeting for native Linux
desktop applications using AT-SPI2 (Assistive Technology Service Provider Interface).
"""

__version__ = "0.1.0"


def main():
    """Entry point for the MCP server."""
    from .server import main as _main

    _main()


__all__ = ["main", "__version__"]
