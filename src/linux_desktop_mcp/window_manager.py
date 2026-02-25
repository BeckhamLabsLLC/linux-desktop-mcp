"""Window group management for targeted desktop automation.

Provides Chrome-extension-like window targeting, allowing Claude to focus on
specific windows instead of the entire desktop, reducing context usage.
"""

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class GroupColor(Enum):
    """Color options for window group borders."""

    BLUE = "#4285F4"
    PURPLE = "#A142F4"
    GREEN = "#34A853"
    ORANGE = "#FA7B17"
    RED = "#EA4335"
    CYAN = "#24C1E0"

    @classmethod
    def from_string(cls, color: str) -> "GroupColor":
        """Get color enum from string name."""
        color_map = {
            "blue": cls.BLUE,
            "purple": cls.PURPLE,
            "green": cls.GREEN,
            "orange": cls.ORANGE,
            "red": cls.RED,
            "cyan": cls.CYAN,
        }
        return color_map.get(color.lower(), cls.BLUE)

    def to_rgb(self) -> tuple[float, float, float]:
        """Convert hex color to RGB floats (0.0-1.0)."""
        hex_color = self.value.lstrip("#")
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return (r, g, b)


@dataclass
class WindowGeometry:
    """Window position and size."""

    x: int
    y: int
    width: int
    height: int

    @property
    def is_valid(self) -> bool:
        """Check if geometry is valid (non-zero size)."""
        return self.width > 0 and self.height > 0

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass
class WindowTarget:
    """Represents a single targeted window."""

    window_id: str
    app_name: str
    window_title: str
    atspi_accessible: Any  # pyatspi.Accessible (frame/window)
    geometry: Optional[WindowGeometry] = None
    is_active: bool = False
    targeted_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for MCP response."""
        return {
            "window_id": self.window_id,
            "app_name": self.app_name,
            "window_title": self.window_title,
            "geometry": self.geometry.to_dict() if self.geometry else None,
            "is_active": self.is_active,
        }

    def is_valid(self) -> bool:
        """Check if the window is still valid (accessible)."""
        if self.atspi_accessible is None:
            return False
        try:
            # Try to access the window - will fail if closed
            self.atspi_accessible.get_state_set()
            return True
        except Exception:
            return False


@dataclass
class WindowGroup:
    """A group of targeted windows (analogous to Chrome tab group)."""

    group_id: str = field(default_factory=lambda: f"grp_{uuid.uuid4().hex[:8]}")
    name: Optional[str] = None
    color: GroupColor = GroupColor.BLUE
    windows: dict[str, WindowTarget] = field(default_factory=dict)
    active_window_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def add_window(self, target: WindowTarget) -> None:
        """Add a window to this group."""
        self.windows[target.window_id] = target
        # First window becomes active automatically
        if self.active_window_id is None:
            self.active_window_id = target.window_id
            target.is_active = True

    def remove_window(self, window_id: str) -> Optional[WindowTarget]:
        """Remove a window from this group."""
        target = self.windows.pop(window_id, None)
        if target:
            target.is_active = False
            # If removed window was active, switch to another
            if self.active_window_id == window_id:
                if self.windows:
                    new_active = next(iter(self.windows.values()))
                    self.active_window_id = new_active.window_id
                    new_active.is_active = True
                else:
                    self.active_window_id = None
        return target

    def set_active_window(self, window_id: str) -> bool:
        """Set a window as the active window in this group."""
        if window_id not in self.windows:
            return False

        # Deactivate current active
        if self.active_window_id and self.active_window_id in self.windows:
            self.windows[self.active_window_id].is_active = False

        # Activate new window
        self.active_window_id = window_id
        self.windows[window_id].is_active = True
        return True

    def get_active_window(self) -> Optional[WindowTarget]:
        """Get the currently active window."""
        if self.active_window_id:
            return self.windows.get(self.active_window_id)
        return None

    def get_all_windows(self) -> list[WindowTarget]:
        """Get all windows in this group."""
        return list(self.windows.values())

    def validate_windows(self) -> list[str]:
        """Check all windows and remove invalid ones. Returns removed window IDs."""
        removed = []
        for window_id, target in list(self.windows.items()):
            if not target.is_valid():
                self.remove_window(window_id)
                removed.append(window_id)
                logger.info(f"Window '{target.window_title}' was closed, removed from group")
        return removed

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for MCP response."""
        return {
            "group_id": self.group_id,
            "name": self.name,
            "color": self.color.name.lower(),
            "color_hex": self.color.value,
            "window_count": len(self.windows),
            "active_window_id": self.active_window_id,
            "windows": [w.to_dict() for w in self.windows.values()],
        }

    def __len__(self) -> int:
        return len(self.windows)


class WindowGroupManager:
    """Manages window groups for the MCP session.

    Provides session-scoped window targeting similar to Chrome's tab groups.
    """

    def __init__(self):
        self._groups: dict[str, WindowGroup] = {}
        self._active_group_id: Optional[str] = None
        self._lock = threading.Lock()
        self._window_counter = 0

    def _generate_window_id(self) -> str:
        """Generate a unique window ID."""
        with self._lock:
            self._window_counter += 1
            return f"win_{self._window_counter}"

    def create_group(
        self, name: Optional[str] = None, color: GroupColor = GroupColor.BLUE
    ) -> WindowGroup:
        """Create a new window group."""
        with self._lock:
            group = WindowGroup(name=name, color=color)
            self._groups[group.group_id] = group
            # First group becomes active automatically
            if self._active_group_id is None:
                self._active_group_id = group.group_id
            return group

    def get_group(self, group_id: str) -> Optional[WindowGroup]:
        """Get a group by ID."""
        with self._lock:
            return self._groups.get(group_id)

    def get_active_group(self) -> Optional[WindowGroup]:
        """Get the currently active group."""
        with self._lock:
            if self._active_group_id:
                return self._groups.get(self._active_group_id)
            return None

    def get_or_create_active_group(self, color: GroupColor = GroupColor.BLUE) -> WindowGroup:
        """Get the active group, creating one if none exists."""
        group = self.get_active_group()
        if group is None:
            group = self.create_group(color=color)
        return group

    def set_active_group(self, group_id: str) -> bool:
        """Set a group as the active group."""
        with self._lock:
            if group_id in self._groups:
                self._active_group_id = group_id
                return True
            return False

    def delete_group(self, group_id: str) -> Optional[WindowGroup]:
        """Delete a group and return it."""
        with self._lock:
            group = self._groups.pop(group_id, None)
            if group is not None and self._active_group_id == group_id:
                # Switch to another group if available
                if self._groups:
                    self._active_group_id = next(iter(self._groups.keys()))
                else:
                    self._active_group_id = None
            return group

    def get_all_groups(self) -> list[WindowGroup]:
        """Get all window groups."""
        with self._lock:
            return list(self._groups.values())

    def add_window_to_active_group(
        self,
        app_name: str,
        window_title: str,
        atspi_accessible: Any,
        geometry: Optional[WindowGeometry] = None,
        color: GroupColor = GroupColor.BLUE,
    ) -> tuple[WindowGroup, WindowTarget]:
        """Add a window to the active group (creates group if needed).

        Returns:
            Tuple of (group, window_target)
        """
        group = self.get_or_create_active_group(color=color)
        window_id = self._generate_window_id()

        target = WindowTarget(
            window_id=window_id,
            app_name=app_name,
            window_title=window_title,
            atspi_accessible=atspi_accessible,
            geometry=geometry,
        )

        group.add_window(target)
        return (group, target)

    def find_window_by_id(self, window_id: str) -> Optional[tuple[WindowGroup, WindowTarget]]:
        """Find a window by ID across all groups."""
        with self._lock:
            for group in self._groups.values():
                if window_id in group.windows:
                    return (group, group.windows[window_id])
            return None

    def release_window(self, window_id: str) -> Optional[WindowTarget]:
        """Release a window from its group."""
        result = self.find_window_by_id(window_id)
        if result:
            group, _ = result
            return group.remove_window(window_id)
        return None

    def release_all_windows(self) -> int:
        """Release all windows from all groups. Returns count released."""
        count = 0
        with self._lock:
            for group in self._groups.values():
                count += len(group.windows)
                group.windows.clear()
                group.active_window_id = None
        return count

    def validate_all_windows(self) -> list[str]:
        """Validate all windows and remove closed ones. Returns removed IDs."""
        removed = []
        with self._lock:
            for group in self._groups.values():
                removed.extend(group.validate_windows())
        return removed

    def clear(self) -> None:
        """Clear all groups and windows."""
        with self._lock:
            self._groups.clear()
            self._active_group_id = None
            self._window_counter = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert manager state to dictionary."""
        with self._lock:
            return {
                "active_group_id": self._active_group_id,
                "group_count": len(self._groups),
                "groups": [g.to_dict() for g in self._groups.values()],
            }
