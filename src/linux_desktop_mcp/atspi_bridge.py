"""Async wrapper for AT-SPI2 accessibility tree access.

pyatspi is synchronous (GLib/D-Bus), so we use ThreadPoolExecutor with locking
to provide async access from the MCP server.
"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Callable, Any
import logging

logger = logging.getLogger(__name__)

# AT-SPI role to ElementRole mapping
ROLE_MAPPING: dict[int, str] = {}

try:
    import gi
    gi.require_version('Atspi', '2.0')
    from gi.repository import Atspi

    ROLE_MAPPING = {
        Atspi.Role.APPLICATION: "application",
        Atspi.Role.FRAME: "frame",
        Atspi.Role.WINDOW: "window",
        Atspi.Role.DIALOG: "dialog",
        Atspi.Role.PANEL: "panel",
        Atspi.Role.TOOL_BAR: "toolbar",
        Atspi.Role.MENU_BAR: "menu_bar",
        Atspi.Role.MENU: "menu",
        Atspi.Role.MENU_ITEM: "menu_item",
        Atspi.Role.PUSH_BUTTON: "push_button",
        Atspi.Role.TOGGLE_BUTTON: "toggle_button",
        Atspi.Role.RADIO_BUTTON: "radio_button",
        Atspi.Role.CHECK_BOX: "check_box",
        Atspi.Role.ENTRY: "entry",
        Atspi.Role.TEXT: "text",
        Atspi.Role.PASSWORD_TEXT: "password_text",
        Atspi.Role.LABEL: "label",
        Atspi.Role.LINK: "link",
        Atspi.Role.LIST: "list",
        Atspi.Role.LIST_ITEM: "list_item",
        Atspi.Role.TABLE: "table",
        Atspi.Role.TABLE_CELL: "table_cell",
        Atspi.Role.TABLE_ROW: "table_row",
        Atspi.Role.TREE: "tree",
        Atspi.Role.TREE_ITEM: "tree_item",
        Atspi.Role.PAGE_TAB_LIST: "tab_list",
        Atspi.Role.PAGE_TAB: "tab",
        Atspi.Role.SCROLL_BAR: "scroll_bar",
        Atspi.Role.SLIDER: "slider",
        Atspi.Role.SPIN_BUTTON: "spin_button",
        Atspi.Role.COMBO_BOX: "combo_box",
        Atspi.Role.IMAGE: "image",
        Atspi.Role.ICON: "icon",
        Atspi.Role.DOCUMENT_FRAME: "document",
        Atspi.Role.DOCUMENT_WEB: "document_web",
        Atspi.Role.SEPARATOR: "separator",
        Atspi.Role.FILLER: "filler",
        Atspi.Role.STATUS_BAR: "status_bar",
        Atspi.Role.PROGRESS_BAR: "progress_bar",
        Atspi.Role.TOOL_TIP: "tooltip",
        Atspi.Role.ALERT: "alert",
        Atspi.Role.NOTIFICATION: "notification",
        Atspi.Role.HEADER: "header",
        Atspi.Role.FOOTER: "footer",
        Atspi.Role.SECTION: "section",
        Atspi.Role.FORM: "form",
        Atspi.Role.PARAGRAPH: "paragraph",
        Atspi.Role.HEADING: "heading",
    }
    ATSPI_AVAILABLE = True
except (ImportError, ValueError) as e:
    logger.warning(f"AT-SPI2 not available: {e}")
    ATSPI_AVAILABLE = False
    Atspi = None


from .references import (
    ElementReference, ElementRole, ElementBounds, ElementState, ReferenceManager
)


def _get_role_from_atspi(atspi_role: int) -> ElementRole:
    """Map AT-SPI role to ElementRole enum."""
    role_str = ROLE_MAPPING.get(atspi_role, "unknown")
    try:
        return ElementRole(role_str)
    except ValueError:
        return ElementRole.UNKNOWN


def _get_state_from_atspi(state_set) -> ElementState:
    """Extract ElementState from AT-SPI StateSet."""
    if not ATSPI_AVAILABLE:
        return ElementState()

    return ElementState(
        visible=state_set.contains(Atspi.StateType.VISIBLE) and
                state_set.contains(Atspi.StateType.SHOWING),
        enabled=state_set.contains(Atspi.StateType.ENABLED) and
                state_set.contains(Atspi.StateType.SENSITIVE),
        focused=state_set.contains(Atspi.StateType.FOCUSED),
        selected=state_set.contains(Atspi.StateType.SELECTED),
        checked=state_set.contains(Atspi.StateType.CHECKED),
        editable=state_set.contains(Atspi.StateType.EDITABLE),
        clickable=state_set.contains(Atspi.StateType.SENSITIVE),
        scrollable=False,  # AT-SPI2 doesn't have direct scrollable state
        expandable=state_set.contains(Atspi.StateType.EXPANDABLE),
        expanded=state_set.contains(Atspi.StateType.EXPANDED),
        has_popup=state_set.contains(Atspi.StateType.HAS_POPUP),
        modal=state_set.contains(Atspi.StateType.MODAL),
        multi_line=state_set.contains(Atspi.StateType.MULTI_LINE),
        required=state_set.contains(Atspi.StateType.REQUIRED),
        invalid=state_set.contains(Atspi.StateType.INVALID_ENTRY),
    )


def _get_bounds_from_atspi(accessible) -> ElementBounds:
    """Get element bounds from AT-SPI accessible."""
    try:
        component = accessible.get_component_iface()
        if component:
            rect = component.get_extents(Atspi.CoordType.SCREEN)
            return ElementBounds(
                x=rect.x,
                y=rect.y,
                width=rect.width,
                height=rect.height
            )
    except Exception:
        pass
    return ElementBounds(x=0, y=0, width=0, height=0)


def _get_available_actions(accessible) -> list[str]:
    """Get available actions for an accessible element."""
    actions = []
    try:
        action_iface = accessible.get_action_iface()
        if action_iface:
            n_actions = action_iface.get_n_actions()
            for i in range(n_actions):
                action_name = action_iface.get_action_name(i)
                if action_name:
                    actions.append(action_name)
    except Exception:
        pass
    return actions


def _get_element_value(accessible) -> Optional[str]:
    """Get the current value of an element if applicable."""
    try:
        value_iface = accessible.get_value_iface()
        if value_iface:
            return str(value_iface.get_current_value())

        text_iface = accessible.get_text_iface()
        if text_iface:
            char_count = text_iface.get_character_count()
            if char_count > 0:
                return text_iface.get_text(0, min(char_count, 1000))
    except Exception:
        pass
    return None


class ATSPIBridge:
    """Async bridge to AT-SPI2 accessibility tree.

    Provides thread-safe async access to pyatspi operations.
    """

    def __init__(self, max_workers: int = 4):
        if not ATSPI_AVAILABLE:
            raise RuntimeError("AT-SPI2 is not available. Install python3-pyatspi gir1.2-atspi-2.0")

        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()
        self._ref_manager = ReferenceManager()

    @property
    def ref_manager(self) -> ReferenceManager:
        """Get the reference manager."""
        return self._ref_manager

    async def _run_sync(self, func: Callable, *args) -> Any:
        """Run a synchronous function in the thread pool."""
        loop = asyncio.get_event_loop()

        def _wrapped():
            with self._lock:
                return func(*args)

        return await loop.run_in_executor(self._executor, _wrapped)

    def _get_desktop_sync(self):
        """Get the desktop accessible (sync)."""
        return Atspi.get_desktop(0)

    async def get_desktop(self):
        """Get the desktop accessible."""
        return await self._run_sync(self._get_desktop_sync)

    def _get_applications_sync(self) -> list:
        """Get all applications (sync)."""
        desktop = Atspi.get_desktop(0)
        apps = []
        if desktop:
            for i in range(desktop.get_child_count()):
                try:
                    child = desktop.get_child_at_index(i)
                    if child:
                        apps.append(child)
                except Exception:
                    pass
        return apps

    async def get_applications(self) -> list:
        """Get all applications."""
        return await self._run_sync(self._get_applications_sync)

    def _build_tree_sync(
        self,
        accessible,
        max_depth: int = 15,
        current_depth: int = 0,
        app_name: Optional[str] = None,
        window_title: Optional[str] = None,
        parent_ref: Optional[str] = None
    ) -> list[ElementReference]:
        """Build element tree from accessible (sync)."""
        refs = []

        if current_depth > max_depth:
            return refs

        try:
            role = accessible.get_role()
            name = accessible.get_name() or ""
            state_set = accessible.get_state_set()
            bounds = _get_bounds_from_atspi(accessible)

            if role == Atspi.Role.APPLICATION:
                app_name = name
            elif role in (Atspi.Role.FRAME, Atspi.Role.WINDOW):
                window_title = name

            ref_id = self._ref_manager.generate_ref_id()
            element_state = _get_state_from_atspi(state_set)

            ref = ElementReference(
                ref_id=ref_id,
                source="atspi",
                role=_get_role_from_atspi(role),
                name=name,
                bounds=bounds,
                state=element_state,
                available_actions=_get_available_actions(accessible),
                description=accessible.get_description() or "",
                value=_get_element_value(accessible),
                atspi_path=str(accessible.get_id()) if hasattr(accessible, 'get_id') else None,
                atspi_accessible=accessible,
                parent_ref=parent_ref,
                app_name=app_name,
                window_title=window_title,
                depth=current_depth,
            )

            self._ref_manager.add(ref)
            refs.append(ref)

            child_count = accessible.get_child_count()
            for i in range(child_count):
                try:
                    child = accessible.get_child_at_index(i)
                    if child:
                        child_refs = self._build_tree_sync(
                            child,
                            max_depth=max_depth,
                            current_depth=current_depth + 1,
                            app_name=app_name,
                            window_title=window_title,
                            parent_ref=ref_id
                        )
                        for child_ref in child_refs:
                            if child_ref.parent_ref == ref_id:
                                ref.child_refs.append(child_ref.ref_id)
                        refs.extend(child_refs)
                except Exception as e:
                    logger.debug(f"Error traversing child {i}: {e}")

        except Exception as e:
            logger.debug(f"Error building tree node: {e}")

        return refs

    async def build_tree(
        self,
        app_name_filter: Optional[str] = None,
        max_depth: int = 15
    ) -> list[ElementReference]:
        """Build the full accessibility tree.

        Args:
            app_name_filter: Only include elements from this application.
            max_depth: Maximum tree traversal depth.

        Returns:
            List of ElementReferences for all discovered elements.
        """
        self._ref_manager.clear()

        def _build():
            all_refs = []
            apps = self._get_applications_sync()

            for app in apps:
                try:
                    app_name = app.get_name() or ""
                    if app_name_filter and app_name_filter.lower() not in app_name.lower():
                        continue

                    refs = self._build_tree_sync(app, max_depth=max_depth)
                    all_refs.extend(refs)
                except Exception as e:
                    logger.debug(f"Error processing app: {e}")

            return all_refs

        return await self._run_sync(_build)

    async def build_tree_for_window(
        self,
        window_accessible,
        max_depth: int = 15
    ) -> list[ElementReference]:
        """Build accessibility tree for a specific window only.

        This provides context reduction - only scanning the targeted window
        rather than the entire desktop.

        Args:
            window_accessible: AT-SPI accessible object for the window/frame.
            max_depth: Maximum tree traversal depth.

        Returns:
            List of ElementReferences for elements within this window.
        """
        self._ref_manager.clear()

        def _build():
            try:
                # Get app name from parent application
                app_name = ""
                try:
                    app = window_accessible.get_application()
                    if app:
                        app_name = app.get_name() or ""
                except Exception:
                    pass

                window_title = window_accessible.get_name() or ""

                return self._build_tree_sync(
                    window_accessible,
                    max_depth=max_depth,
                    app_name=app_name,
                    window_title=window_title
                )
            except Exception as e:
                logger.error(f"Error building tree for window: {e}")
                return []

        return await self._run_sync(_build)

    async def build_tree_for_windows(
        self,
        window_accessibles: list,
        max_depth: int = 15
    ) -> list[ElementReference]:
        """Build accessibility tree for multiple windows.

        Args:
            window_accessibles: List of AT-SPI accessible objects for windows.
            max_depth: Maximum tree traversal depth.

        Returns:
            List of ElementReferences for elements within all specified windows.
        """
        self._ref_manager.clear()

        def _build():
            all_refs = []
            for window_accessible in window_accessibles:
                try:
                    # Get app name from parent application
                    app_name = ""
                    try:
                        app = window_accessible.get_application()
                        if app:
                            app_name = app.get_name() or ""
                    except Exception:
                        pass

                    window_title = window_accessible.get_name() or ""

                    refs = self._build_tree_sync(
                        window_accessible,
                        max_depth=max_depth,
                        app_name=app_name,
                        window_title=window_title
                    )
                    all_refs.extend(refs)
                except Exception as e:
                    logger.debug(f"Error processing window: {e}")
            return all_refs

        return await self._run_sync(_build)

    def _click_element_sync(self, accessible, button: str = "left") -> bool:
        """Click an element using AT-SPI action interface (sync)."""
        try:
            action_iface = accessible.get_action_iface()
            if action_iface:
                n_actions = action_iface.get_n_actions()
                for i in range(n_actions):
                    action_name = action_iface.get_action_name(i)
                    if action_name in ("click", "activate", "press"):
                        return action_iface.do_action(i)

            component = accessible.get_component_iface()
            if component:
                return component.grab_focus()

        except Exception as e:
            logger.error(f"Error clicking element: {e}")

        return False

    async def click_element(self, ref: ElementReference, button: str = "left") -> bool:
        """Click an element by reference.

        Args:
            ref: Element reference to click.
            button: Mouse button ("left", "right", "middle").

        Returns:
            True if click succeeded via AT-SPI action.
        """
        if ref.atspi_accessible is None:
            return False

        return await self._run_sync(self._click_element_sync, ref.atspi_accessible, button)

    def _focus_element_sync(self, accessible) -> bool:
        """Focus an element (sync)."""
        try:
            component = accessible.get_component_iface()
            if component:
                return component.grab_focus()
        except Exception as e:
            logger.error(f"Error focusing element: {e}")
        return False

    async def focus_element(self, ref: ElementReference) -> bool:
        """Focus an element by reference."""
        if ref.atspi_accessible is None:
            return False

        return await self._run_sync(self._focus_element_sync, ref.atspi_accessible)

    def _set_text_sync(self, accessible, text: str, clear_first: bool = True) -> bool:
        """Set text in an editable element (sync)."""
        try:
            editable = accessible.get_editable_text_iface()
            if editable:
                if clear_first:
                    text_iface = accessible.get_text_iface()
                    if text_iface:
                        char_count = text_iface.get_character_count()
                        if char_count > 0:
                            editable.delete_text(0, char_count)

                return editable.insert_text(0, text, len(text))
        except Exception as e:
            logger.error(f"Error setting text: {e}")
        return False

    async def set_text(self, ref: ElementReference, text: str, clear_first: bool = True) -> bool:
        """Set text in an editable element.

        Args:
            ref: Element reference.
            text: Text to set.
            clear_first: Whether to clear existing text first.

        Returns:
            True if text was set successfully.
        """
        if ref.atspi_accessible is None:
            return False

        return await self._run_sync(self._set_text_sync, ref.atspi_accessible, text, clear_first)

    def _get_element_at_point_sync(self, x: int, y: int):
        """Get element at screen coordinates (sync)."""
        desktop = Atspi.get_desktop(0)
        if not desktop:
            return None

        for i in range(desktop.get_child_count()):
            try:
                app = desktop.get_child_at_index(i)
                if app:
                    component = app.get_component_iface()
                    if component:
                        accessible = component.get_accessible_at_point(
                            x, y, Atspi.CoordType.SCREEN
                        )
                        if accessible:
                            return accessible
            except Exception:
                pass
        return None

    async def get_element_at_point(self, x: int, y: int) -> Optional[ElementReference]:
        """Get the element at screen coordinates.

        Args:
            x: X coordinate.
            y: Y coordinate.

        Returns:
            ElementReference at the point, or None.
        """
        accessible = await self._run_sync(self._get_element_at_point_sync, x, y)
        if accessible:
            refs = await self._run_sync(self._build_tree_sync, accessible, max_depth=0)
            if refs:
                return refs[0]
        return None

    async def shutdown(self):
        """Shutdown the bridge and cleanup resources."""
        self._executor.shutdown(wait=True)
        self._ref_manager.clear()
