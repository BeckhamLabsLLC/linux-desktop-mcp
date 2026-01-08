"""Element reference system for desktop automation.

Provides a reference management system similar to Chrome extension's ref_id system,
allowing semantic element targeting by reference instead of coordinates.
"""

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ElementRole(Enum):
    """Standard element roles from AT-SPI."""

    APPLICATION = "application"
    FRAME = "frame"
    WINDOW = "window"
    DIALOG = "dialog"
    PANEL = "panel"
    TOOLBAR = "toolbar"
    MENU_BAR = "menu_bar"
    MENU = "menu"
    MENU_ITEM = "menu_item"
    BUTTON = "button"
    PUSH_BUTTON = "push_button"
    TOGGLE_BUTTON = "toggle_button"
    RADIO_BUTTON = "radio_button"
    CHECK_BOX = "check_box"
    ENTRY = "entry"
    TEXT = "text"
    PASSWORD_TEXT = "password_text"
    LABEL = "label"
    LINK = "link"
    LIST = "list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    TABLE_CELL = "table_cell"
    TABLE_ROW = "table_row"
    TREE = "tree"
    TREE_ITEM = "tree_item"
    TAB_LIST = "tab_list"
    TAB = "tab"
    SCROLL_BAR = "scroll_bar"
    SLIDER = "slider"
    SPIN_BUTTON = "spin_button"
    COMBO_BOX = "combo_box"
    IMAGE = "image"
    ICON = "icon"
    DOCUMENT = "document"
    DOCUMENT_WEB = "document_web"
    SEPARATOR = "separator"
    FILLER = "filler"
    STATUS_BAR = "status_bar"
    PROGRESS_BAR = "progress_bar"
    TOOLTIP = "tooltip"
    ALERT = "alert"
    NOTIFICATION = "notification"
    HEADER = "header"
    FOOTER = "footer"
    SECTION = "section"
    FORM = "form"
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    # OCR-specific
    OCR_TEXT = "ocr_text"
    # Unknown/fallback
    UNKNOWN = "unknown"


@dataclass
class ElementBounds:
    """Screen position and size of an element."""

    x: int
    y: int
    width: int
    height: int

    @property
    def center(self) -> tuple[int, int]:
        """Get the center point of the element."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def is_valid(self) -> bool:
        """Check if bounds are valid (non-negative position and non-zero size)."""
        return (
            self.x >= 0
            and self.y >= 0
            and self.width > 0
            and self.height > 0
            and self.width < 65536
            and self.height < 65536
        )

    def contains_point(self, x: int, y: int) -> bool:
        """Check if a point is within the bounds."""
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height

    def overlaps(self, other: "ElementBounds", threshold: float = 0.7) -> bool:
        """Check if this bounds overlaps with another by at least threshold."""
        x_overlap = max(0, min(self.x + self.width, other.x + other.width) - max(self.x, other.x))
        y_overlap = max(0, min(self.y + self.height, other.y + other.height) - max(self.y, other.y))
        overlap_area = x_overlap * y_overlap
        self_area = self.width * self.height
        if self_area == 0:
            return False
        return overlap_area / self_area >= threshold


@dataclass
class ElementState:
    """State flags for an element."""

    visible: bool = True
    enabled: bool = True
    focused: bool = False
    selected: bool = False
    checked: bool = False
    editable: bool = False
    clickable: bool = False
    scrollable: bool = False
    expandable: bool = False
    expanded: bool = False
    has_popup: bool = False
    modal: bool = False
    multi_line: bool = False
    required: bool = False
    invalid: bool = False

    def to_list(self) -> list[str]:
        """Return a list of active state names."""
        states = []
        if not self.visible:
            states.append("hidden")
        if not self.enabled:
            states.append("disabled")
        if self.focused:
            states.append("focused")
        if self.selected:
            states.append("selected")
        if self.checked:
            states.append("checked")
        if self.editable:
            states.append("editable")
        if self.clickable:
            states.append("clickable")
        if self.scrollable:
            states.append("scrollable")
        if self.expandable:
            states.append("expandable")
        if self.expanded:
            states.append("expanded")
        if self.has_popup:
            states.append("has_popup")
        if self.modal:
            states.append("modal")
        if self.multi_line:
            states.append("multi_line")
        if self.required:
            states.append("required")
        if self.invalid:
            states.append("invalid")
        return states


@dataclass
class ElementReference:
    """Reference to a UI element."""

    ref_id: str
    source: str  # "atspi" or "ocr"
    role: ElementRole
    name: str
    bounds: ElementBounds
    state: ElementState
    available_actions: list[str] = field(default_factory=list)
    description: str = ""
    value: Optional[str] = None
    # AT-SPI specific
    atspi_path: Optional[str] = None
    atspi_accessible: Optional[Any] = None  # pyatspi.Accessible
    # OCR specific
    ocr_confidence: Optional[float] = None
    # Hierarchy
    parent_ref: Optional[str] = None
    child_refs: list[str] = field(default_factory=list)
    # Metadata
    app_name: Optional[str] = None
    window_title: Optional[str] = None
    depth: int = 0
    created_at: float = field(default_factory=time.time)

    def format_for_display(self, indent: int = 0) -> str:
        """Format element for display in snapshot output."""
        prefix = "  " * indent
        state_str = ""
        states = self.state.to_list()
        if states:
            state_str = f" ({', '.join(states)})"

        name_str = f' "{self.name}"' if self.name else ""
        role_str = f"[{self.role.value}]"

        return f"{prefix}- {self.ref_id}: {role_str}{name_str}{state_str}"

    def matches_query(self, query: str) -> bool:
        """Check if this element matches a natural language query."""
        query_lower = query.lower()

        if self.name and query_lower in self.name.lower():
            return True

        if query_lower in self.role.value.replace("_", " "):
            return True

        if self.description and query_lower in self.description.lower():
            return True

        return False


class ReferenceManager:
    """Manages element references with garbage collection.

    References are session-scoped and garbage collected after a timeout.
    """

    DEFAULT_TTL = 300  # 5 minutes
    GC_INTERVAL = 30  # Run GC at most every 30 seconds

    def __init__(self, ttl: float = DEFAULT_TTL):
        self._refs: dict[str, ElementReference] = {}
        self._counter = 0
        self._lock = threading.Lock()
        self._ttl = ttl
        self._last_gc = time.time()

    def clear(self) -> None:
        """Clear all references."""
        with self._lock:
            self._refs.clear()
            self._counter = 0

    def generate_ref_id(self) -> str:
        """Generate a new reference ID."""
        with self._lock:
            self._counter += 1
            return f"ref_{self._counter}"

    def add(self, ref: ElementReference) -> str:
        """Add a reference and return its ID."""
        with self._lock:
            self._refs[ref.ref_id] = ref
            return ref.ref_id

    def get(self, ref_id: str) -> Optional[ElementReference]:
        """Get a reference by ID, returning None if expired or not found."""
        # Trigger periodic GC
        now = time.time()
        if now - self._last_gc > self.GC_INTERVAL:
            self._gc()
            self._last_gc = now

        with self._lock:
            ref = self._refs.get(ref_id)
            if ref is None:
                return None

            if time.time() - ref.created_at > self._ttl:
                del self._refs[ref_id]
                return None

            return ref

    def get_all(self) -> list[ElementReference]:
        """Get all valid references."""
        self._gc()
        with self._lock:
            return list(self._refs.values())

    def find_by_role(self, role: ElementRole) -> list[ElementReference]:
        """Find all references with a specific role."""
        return [ref for ref in self.get_all() if ref.role == role]

    def find_by_name(self, name: str, partial: bool = True) -> list[ElementReference]:
        """Find references by name."""
        results = []
        name_lower = name.lower()
        for ref in self.get_all():
            if ref.name:
                if partial and name_lower in ref.name.lower():
                    results.append(ref)
                elif not partial and name_lower == ref.name.lower():
                    results.append(ref)
        return results

    def find_by_query(self, query: str) -> list[ElementReference]:
        """Find references matching a natural language query."""
        return [ref for ref in self.get_all() if ref.matches_query(query)]

    def find_at_point(self, x: int, y: int) -> list[ElementReference]:
        """Find all elements at a screen coordinate."""
        results = []
        for ref in self.get_all():
            if ref.bounds.contains_point(x, y):
                results.append(ref)
        return sorted(results, key=lambda r: r.depth, reverse=True)

    def _gc(self) -> int:
        """Garbage collect expired references. Returns count of removed refs."""
        now = time.time()
        expired = []
        with self._lock:
            for ref_id, ref in self._refs.items():
                if now - ref.created_at > self._ttl:
                    expired.append(ref_id)
            for ref_id in expired:
                del self._refs[ref_id]
        return len(expired)

    def __len__(self) -> int:
        """Return number of active references."""
        self._gc()
        with self._lock:
            return len(self._refs)
