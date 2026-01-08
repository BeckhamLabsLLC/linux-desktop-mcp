"""AT-SPI2 window discovery utilities.

Provides functions to enumerate and find windows using AT-SPI2 accessibility API.
"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Any, Callable
from dataclasses import dataclass
import logging

from .window_manager import WindowGeometry

logger = logging.getLogger(__name__)

# AT-SPI2 availability check
ATSPI_AVAILABLE = False
Atspi = None

try:
    import gi
    gi.require_version('Atspi', '2.0')
    from gi.repository import Atspi
    ATSPI_AVAILABLE = True
except (ImportError, ValueError) as e:
    logger.warning(f"AT-SPI2 not available: {e}")


@dataclass
class WindowInfo:
    """Information about a discovered window."""
    app_name: str
    window_title: str
    atspi_accessible: Any  # Atspi.Accessible
    geometry: Optional[WindowGeometry]
    is_active: bool
    is_focused: bool
    pid: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for MCP response."""
        return {
            "app_name": self.app_name,
            "window_title": self.window_title,
            "geometry": self.geometry.to_dict() if self.geometry else None,
            "is_active": self.is_active,
            "is_focused": self.is_focused,
            "pid": self.pid,
        }


class WindowDiscovery:
    """AT-SPI2 based window discovery.

    Provides async methods to enumerate and find windows across the desktop.
    """

    def __init__(self, max_workers: int = 2):
        if not ATSPI_AVAILABLE:
            raise RuntimeError("AT-SPI2 is not available")
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()

    async def _run_sync(self, func: Callable, *args) -> Any:
        """Run a synchronous function in the thread pool."""
        loop = asyncio.get_event_loop()

        def _wrapped():
            with self._lock:
                return func(*args)

        return await loop.run_in_executor(self._executor, _wrapped)

    def _get_window_geometry_sync(self, accessible) -> Optional[WindowGeometry]:
        """Get window geometry from accessible (sync)."""
        try:
            component = accessible.get_component_iface()
            if component:
                rect = component.get_extents(Atspi.CoordType.SCREEN)
                return WindowGeometry(
                    x=rect.x,
                    y=rect.y,
                    width=rect.width,
                    height=rect.height
                )
        except Exception:
            pass
        return None

    def _enumerate_windows_sync(self) -> list[WindowInfo]:
        """Enumerate all visible windows (sync)."""
        windows = []
        desktop = Atspi.get_desktop(0)

        if not desktop:
            return windows

        # Iterate through all applications
        for app_idx in range(desktop.get_child_count()):
            try:
                app = desktop.get_child_at_index(app_idx)
                if not app:
                    continue

                app_name = app.get_name() or ""

                # Skip certain system applications
                if app_name in ("", "mutter", "gnome-shell", "plasmashell"):
                    continue

                # Get process ID if available
                pid = None
                try:
                    pid = app.get_process_id()
                except Exception:
                    pass

                # Iterate through app's children (windows/frames)
                for win_idx in range(app.get_child_count()):
                    try:
                        window = app.get_child_at_index(win_idx)
                        if not window:
                            continue

                        role = window.get_role()

                        # Filter to frame/window roles
                        if role not in (Atspi.Role.FRAME, Atspi.Role.WINDOW):
                            continue

                        state_set = window.get_state_set()

                        # Skip non-visible windows
                        if not state_set.contains(Atspi.StateType.VISIBLE):
                            continue

                        # Skip minimized windows (not showing)
                        if not state_set.contains(Atspi.StateType.SHOWING):
                            continue

                        window_title = window.get_name() or ""
                        geometry = self._get_window_geometry_sync(window)

                        # Skip windows with invalid geometry
                        if geometry and not geometry.is_valid:
                            continue

                        windows.append(WindowInfo(
                            app_name=app_name,
                            window_title=window_title,
                            atspi_accessible=window,
                            geometry=geometry,
                            is_active=state_set.contains(Atspi.StateType.ACTIVE),
                            is_focused=state_set.contains(Atspi.StateType.FOCUSED),
                            pid=pid,
                        ))

                    except Exception as e:
                        logger.debug(f"Error processing window: {e}")
                        continue

            except Exception as e:
                logger.debug(f"Error processing app: {e}")
                continue

        return windows

    async def enumerate_windows(self) -> list[WindowInfo]:
        """Enumerate all visible windows on the desktop.

        Returns:
            List of WindowInfo for each discovered window.
        """
        return await self._run_sync(self._enumerate_windows_sync)

    def _find_window_by_title_sync(
        self,
        title_pattern: str,
        app_name: Optional[str] = None
    ) -> list[WindowInfo]:
        """Find windows matching title pattern (sync)."""
        all_windows = self._enumerate_windows_sync()
        matches = []
        title_lower = title_pattern.lower()

        for window in all_windows:
            # Filter by app name if provided
            if app_name and app_name.lower() not in window.app_name.lower():
                continue

            # Match title
            if title_lower in window.window_title.lower():
                matches.append(window)

        return matches

    async def find_window_by_title(
        self,
        title_pattern: str,
        app_name: Optional[str] = None
    ) -> list[WindowInfo]:
        """Find windows matching a title pattern.

        Args:
            title_pattern: Partial title to match (case-insensitive)
            app_name: Optional app name filter

        Returns:
            List of matching WindowInfo objects.
        """
        return await self._run_sync(
            self._find_window_by_title_sync,
            title_pattern,
            app_name
        )

    def _find_windows_by_app_sync(self, app_name: str) -> list[WindowInfo]:
        """Find all windows for an application (sync)."""
        all_windows = self._enumerate_windows_sync()
        app_lower = app_name.lower()

        return [
            w for w in all_windows
            if app_lower in w.app_name.lower()
        ]

    async def find_windows_by_app(self, app_name: str) -> list[WindowInfo]:
        """Find all windows for a specific application.

        Args:
            app_name: Application name to filter by (case-insensitive partial match)

        Returns:
            List of WindowInfo for matching application.
        """
        return await self._run_sync(self._find_windows_by_app_sync, app_name)

    def _get_focused_window_sync(self) -> Optional[WindowInfo]:
        """Get the currently focused window (sync)."""
        all_windows = self._enumerate_windows_sync()

        for window in all_windows:
            if window.is_focused:
                return window

        # Fallback to active window if no focused window found
        for window in all_windows:
            if window.is_active:
                return window

        return None

    async def get_focused_window(self) -> Optional[WindowInfo]:
        """Get the currently focused window.

        Returns:
            WindowInfo for the focused window, or None if none found.
        """
        return await self._run_sync(self._get_focused_window_sync)

    def _refresh_window_geometry_sync(self, accessible) -> Optional[WindowGeometry]:
        """Refresh geometry for an accessible window (sync)."""
        return self._get_window_geometry_sync(accessible)

    async def refresh_window_geometry(self, accessible) -> Optional[WindowGeometry]:
        """Refresh the geometry for a window accessible.

        Args:
            accessible: AT-SPI accessible object for the window

        Returns:
            Updated WindowGeometry or None if unable to get geometry.
        """
        return await self._run_sync(self._refresh_window_geometry_sync, accessible)

    def _is_window_valid_sync(self, accessible) -> bool:
        """Check if a window is still valid (sync)."""
        try:
            state_set = accessible.get_state_set()
            return (
                state_set.contains(Atspi.StateType.VISIBLE) and
                state_set.contains(Atspi.StateType.SHOWING)
            )
        except Exception:
            return False

    async def is_window_valid(self, accessible) -> bool:
        """Check if a window accessible is still valid.

        Args:
            accessible: AT-SPI accessible object for the window

        Returns:
            True if window is still valid and visible.
        """
        return await self._run_sync(self._is_window_valid_sync, accessible)

    def shutdown(self):
        """Shutdown the discovery executor."""
        self._executor.shutdown(wait=True)
