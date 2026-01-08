"""Border overlay system for visual window targeting.

Provides visual indicators (colored borders) around targeted windows,
similar to Chrome extension's tab group coloring.
"""

import threading
import logging
import atexit
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass

from .window_manager import WindowGeometry, GroupColor
from .detection import DisplayServer

logger = logging.getLogger(__name__)

# GTK availability flags
GTK3_AVAILABLE = False
GTK4_AVAILABLE = False
LAYER_SHELL_AVAILABLE = False
Gtk = None
Gdk = None
GLib = None

try:
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('Gdk', '3.0')
    from gi.repository import Gtk as _Gtk, Gdk as _Gdk, GLib as _GLib
    Gtk = _Gtk
    Gdk = _Gdk
    GLib = _GLib
    GTK3_AVAILABLE = True
except (ImportError, ValueError) as e:
    logger.debug(f"GTK3 not available: {e}")

try:
    import gi
    gi.require_version('Gtk4LayerShell', '1.0')
    from gi.repository import Gtk4LayerShell
    LAYER_SHELL_AVAILABLE = True
except (ImportError, ValueError) as e:
    logger.debug(f"gtk4-layer-shell not available: {e}")


class GtkThread:
    """Background thread for running the GTK main loop.

    This allows GTK windows (like border overlays) to be created and
    updated from non-GTK threads by scheduling operations via GLib.idle_add().
    """

    _instance: Optional["GtkThread"] = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern - only one GTK thread per process."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._started = threading.Event()
        self._initialized = True

        # Register cleanup on exit
        atexit.register(self.stop)

    def start(self) -> bool:
        """Start the GTK main loop in a background thread.

        Returns:
            True if started successfully or already running.
        """
        if not GTK3_AVAILABLE:
            logger.warning("Cannot start GTK thread: GTK3 not available")
            return False

        with self._lock:
            if self._running:
                return True

            self._running = True
            self._started.clear()

            self._thread = threading.Thread(
                target=self._run_gtk_main,
                name="GtkMainLoop",
                daemon=True
            )
            self._thread.start()

            # Wait for GTK to initialize (max 2 seconds)
            if not self._started.wait(timeout=2.0):
                logger.warning("GTK main loop took too long to start")
                return False

            logger.info("GTK background thread started")
            return True

    def _run_gtk_main(self):
        """Run the GTK main loop (called in background thread)."""
        try:
            # Initialize GTK
            if not Gtk.init_check()[0]:
                logger.error("GTK init failed")
                self._running = False
                self._started.set()
                return

            # Signal that we're ready
            self._started.set()

            # Run the main loop
            while self._running:
                # Process pending events with a timeout
                # This allows us to check _running periodically
                while Gtk.events_pending():
                    Gtk.main_iteration_do(False)

                # Small sleep to prevent busy-waiting
                import time
                time.sleep(0.01)

        except Exception as e:
            logger.error(f"GTK main loop error: {e}")
        finally:
            self._running = False
            logger.debug("GTK main loop exited")

    def stop(self):
        """Stop the GTK main loop."""
        with self._lock:
            if not self._running:
                return

            self._running = False

            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.0)

            logger.debug("GTK thread stopped")

    @property
    def is_running(self) -> bool:
        """Check if the GTK thread is running."""
        return self._running

    def schedule(self, func, *args) -> bool:
        """Schedule a function to run on the GTK thread.

        Args:
            func: Function to call
            *args: Arguments to pass to the function

        Returns:
            True if scheduled successfully.
        """
        if not self._running:
            if not self.start():
                return False

        def wrapper():
            try:
                func(*args)
            except Exception as e:
                logger.error(f"Error in GTK scheduled function: {e}")
            return False  # Don't repeat

        GLib.idle_add(wrapper)
        return True


# Global GTK thread instance
_gtk_thread: Optional[GtkThread] = None

def get_gtk_thread() -> Optional[GtkThread]:
    """Get or create the global GTK thread."""
    global _gtk_thread
    if not GTK3_AVAILABLE:
        return None
    if _gtk_thread is None:
        _gtk_thread = GtkThread()
    return _gtk_thread


# Border configuration
BORDER_THICKNESS = 4  # pixels


@dataclass
class BorderWindows:
    """Container for the 4 border windows around a target."""
    top: Any = None      # GTK Window
    bottom: Any = None
    left: Any = None
    right: Any = None
    window_id: str = ""

    def destroy_all(self):
        """Destroy all border windows."""
        for window in [self.top, self.bottom, self.left, self.right]:
            if window:
                try:
                    window.destroy()
                except Exception:
                    pass
        self.top = self.bottom = self.left = self.right = None


class OverlayBackend(ABC):
    """Abstract base class for overlay backends."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is available on the current system."""
        pass

    @abstractmethod
    def show_border(
        self,
        window_id: str,
        geometry: WindowGeometry,
        color: GroupColor
    ) -> bool:
        """Show a colored border around a window.

        Args:
            window_id: Unique ID for this border (for tracking)
            geometry: Position and size of the target window
            color: Border color

        Returns:
            True if border was shown successfully.
        """
        pass

    @abstractmethod
    def hide_border(self, window_id: str) -> bool:
        """Hide the border for a specific window.

        Args:
            window_id: The window ID whose border to hide

        Returns:
            True if border was hidden.
        """
        pass

    @abstractmethod
    def hide_all_borders(self) -> None:
        """Hide all borders."""
        pass

    @abstractmethod
    def update_border_position(
        self,
        window_id: str,
        geometry: WindowGeometry
    ) -> bool:
        """Update the position of an existing border.

        Args:
            window_id: The window ID whose border to update
            geometry: New position and size

        Returns:
            True if border was updated.
        """
        pass


class X11OverlayBackend(OverlayBackend):
    """X11 overlay backend using GTK3 with override-redirect windows.

    Creates 4 thin overlay windows (top, bottom, left, right) around
    the target window to form a colored border. Uses a background GTK
    thread to handle window rendering.
    """

    def __init__(self):
        if not GTK3_AVAILABLE:
            raise RuntimeError("GTK3 not available")

        self._borders: Dict[str, BorderWindows] = {}
        self._lock = threading.Lock()
        self._gtk_thread = get_gtk_thread()

        # Start the GTK thread
        if self._gtk_thread:
            self._gtk_thread.start()

    def is_available(self) -> bool:
        return GTK3_AVAILABLE and self._gtk_thread is not None

    def _create_border_window(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        color: GroupColor
    ) -> Any:
        """Create a single border window. Must be called from GTK thread."""
        window = Gtk.Window(type=Gtk.WindowType.POPUP)
        window.set_decorated(False)
        window.set_skip_taskbar_hint(True)
        window.set_skip_pager_hint(True)
        window.set_keep_above(True)
        window.set_accept_focus(False)

        # Enable transparency
        screen = window.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            window.set_visual(visual)
        window.set_app_paintable(True)

        # Connect draw signal
        r, g, b = color.to_rgb()
        window.connect('draw', lambda w, cr: self._draw_border(cr, r, g, b))

        # Make click-through after realization
        window.connect('realize', self._make_click_through)

        # Position and size
        window.move(x, y)
        window.set_default_size(width, height)
        window.resize(width, height)

        return window

    def _draw_border(self, cr, r: float, g: float, b: float) -> bool:
        """Draw the border color."""
        cr.set_source_rgba(r, g, b, 1.0)
        cr.paint()
        return False

    def _make_click_through(self, window):
        """Make the window click-through using input shape."""
        try:
            # Create an empty region for input - clicks pass through
            import cairo
            region = cairo.Region()
            window.input_shape_combine_region(region)
        except Exception as e:
            logger.debug(f"Could not set click-through: {e}")

    def show_border(
        self,
        window_id: str,
        geometry: WindowGeometry,
        color: GroupColor
    ) -> bool:
        """Show a colored border around a window."""
        if not self._gtk_thread or not self._gtk_thread.is_running:
            if not self._gtk_thread or not self._gtk_thread.start():
                logger.warning("GTK thread not available for border overlay")
                return False

        # Prepare border data
        x, y, w, h = geometry.x, geometry.y, geometry.width, geometry.height
        t = BORDER_THICKNESS

        # Create a result holder for thread synchronization
        result = {"success": False, "done": threading.Event()}

        def create_borders():
            try:
                with self._lock:
                    # Hide existing border for this window if any
                    if window_id in self._borders:
                        self._borders[window_id].destroy_all()

                    borders = BorderWindows(window_id=window_id)

                    # Create 4 border windows
                    borders.top = self._create_border_window(
                        x - t, y - t, w + 2*t, t, color
                    )
                    borders.bottom = self._create_border_window(
                        x - t, y + h, w + 2*t, t, color
                    )
                    borders.left = self._create_border_window(
                        x - t, y, t, h, color
                    )
                    borders.right = self._create_border_window(
                        x + w, y, t, h, color
                    )

                    # Show all windows
                    for win in [borders.top, borders.bottom, borders.left, borders.right]:
                        if win:
                            win.show_all()

                    self._borders[window_id] = borders
                    result["success"] = True
                    logger.info(f"Border overlay shown for {window_id}")

            except Exception as e:
                logger.error(f"Failed to create border overlay: {e}")
                result["success"] = False
            finally:
                result["done"].set()

        # Schedule on GTK thread
        self._gtk_thread.schedule(create_borders)

        # Wait for completion (with timeout)
        result["done"].wait(timeout=2.0)
        return result["success"]

    def hide_border(self, window_id: str) -> bool:
        """Hide the border for a specific window."""
        with self._lock:
            if window_id not in self._borders:
                return False

            borders = self._borders.pop(window_id)

        def destroy():
            borders.destroy_all()
            logger.debug(f"Border overlay hidden for {window_id}")

        if self._gtk_thread and self._gtk_thread.is_running:
            self._gtk_thread.schedule(destroy)
        else:
            # Fallback: destroy directly (may cause issues if not on GTK thread)
            destroy()

        return True

    def hide_all_borders(self) -> None:
        """Hide all borders."""
        with self._lock:
            borders_to_destroy = list(self._borders.values())
            self._borders.clear()

        def destroy_all():
            for borders in borders_to_destroy:
                borders.destroy_all()
            logger.debug("All border overlays hidden")

        if self._gtk_thread and self._gtk_thread.is_running:
            self._gtk_thread.schedule(destroy_all)
        else:
            destroy_all()

    def update_border_position(
        self,
        window_id: str,
        geometry: WindowGeometry
    ) -> bool:
        """Update the position of an existing border."""
        with self._lock:
            if window_id not in self._borders:
                return False
            borders = self._borders[window_id]

        x, y, w, h = geometry.x, geometry.y, geometry.width, geometry.height
        t = BORDER_THICKNESS

        def update():
            try:
                if borders.top:
                    borders.top.move(x - t, y - t)
                    borders.top.resize(w + 2*t, t)
                if borders.bottom:
                    borders.bottom.move(x - t, y + h)
                    borders.bottom.resize(w + 2*t, t)
                if borders.left:
                    borders.left.move(x - t, y)
                    borders.left.resize(t, h)
                if borders.right:
                    borders.right.move(x + w, y)
                    borders.right.resize(t, h)
            except Exception as e:
                logger.debug(f"Error updating border position: {e}")

        if self._gtk_thread and self._gtk_thread.is_running:
            self._gtk_thread.schedule(update)
            return True
        return False

    def shutdown(self):
        """Shutdown the backend and cleanup resources."""
        self.hide_all_borders()
        # Note: Don't stop the GTK thread here as it's shared


class WaylandLayerShellBackend(OverlayBackend):
    """Wayland overlay backend using gtk4-layer-shell.

    Works on wlroots-compatible compositors (Sway, Hyprland, KDE Plasma, etc).
    Does NOT work on GNOME Wayland.
    """

    def __init__(self):
        if not LAYER_SHELL_AVAILABLE:
            raise RuntimeError("gtk4-layer-shell not available")
        self._borders: Dict[str, BorderWindows] = {}
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        if not LAYER_SHELL_AVAILABLE:
            return False
        try:
            # Check if layer shell is actually supported by compositor
            return Gtk4LayerShell.is_supported()
        except Exception:
            return False

    def show_border(
        self,
        window_id: str,
        geometry: WindowGeometry,
        color: GroupColor
    ) -> bool:
        """Show border using layer shell - placeholder for now."""
        # Layer shell positioning is complex - for now return False
        # and let the manager fall back to no visual indicator
        logger.info("Wayland layer-shell border: not yet fully implemented")
        return False

    def hide_border(self, window_id: str) -> bool:
        with self._lock:
            if window_id in self._borders:
                self._borders[window_id].destroy_all()
                del self._borders[window_id]
                return True
            return False

    def hide_all_borders(self) -> None:
        with self._lock:
            for borders in self._borders.values():
                borders.destroy_all()
            self._borders.clear()

    def update_border_position(
        self,
        window_id: str,
        geometry: WindowGeometry
    ) -> bool:
        return False


class NoOverlayBackend(OverlayBackend):
    """Fallback backend when no overlay support is available.

    Used for GNOME Wayland or when GTK is unavailable.
    """

    def __init__(self, reason: str = "No overlay support available"):
        self._reason = reason

    def is_available(self) -> bool:
        return False

    def show_border(
        self,
        window_id: str,
        geometry: WindowGeometry,
        color: GroupColor
    ) -> bool:
        logger.info(f"Border overlay not shown: {self._reason}")
        return False

    def hide_border(self, window_id: str) -> bool:
        return True

    def hide_all_borders(self) -> None:
        pass

    def update_border_position(
        self,
        window_id: str,
        geometry: WindowGeometry
    ) -> bool:
        return False


class OverlayManager:
    """Factory and manager for overlay backends.

    Selects the appropriate backend based on display server and
    available libraries.
    """

    def __init__(self, display_server: DisplayServer):
        self._display_server = display_server
        self._backend = self._select_backend()
        logger.info(f"Overlay backend: {type(self._backend).__name__}")

    def _select_backend(self) -> OverlayBackend:
        """Select the appropriate backend for the current environment."""
        if self._display_server == DisplayServer.X11:
            if GTK3_AVAILABLE:
                try:
                    backend = X11OverlayBackend()
                    return backend
                except Exception as e:
                    logger.warning(f"Failed to init X11 overlay: {e}")

        elif self._display_server in (DisplayServer.WAYLAND, DisplayServer.XWAYLAND):
            # Try layer shell for Wayland
            if LAYER_SHELL_AVAILABLE:
                try:
                    backend = WaylandLayerShellBackend()
                    if backend.is_available():
                        return backend
                except Exception as e:
                    logger.debug(f"Layer shell not available: {e}")

            # XWayland can use X11 backend
            if self._display_server == DisplayServer.XWAYLAND and GTK3_AVAILABLE:
                try:
                    return X11OverlayBackend()
                except Exception as e:
                    logger.debug(f"X11 overlay on XWayland failed: {e}")

            # GNOME Wayland or unsupported compositor
            return NoOverlayBackend("GNOME Wayland does not support window overlays")

        return NoOverlayBackend("No compatible overlay backend found")

    @property
    def backend(self) -> OverlayBackend:
        """Get the active backend."""
        return self._backend

    @property
    def has_visual_support(self) -> bool:
        """Check if visual overlays are supported."""
        return self._backend.is_available()

    def show_border(
        self,
        window_id: str,
        geometry: WindowGeometry,
        color: GroupColor
    ) -> bool:
        """Show a border around a window."""
        return self._backend.show_border(window_id, geometry, color)

    def hide_border(self, window_id: str) -> bool:
        """Hide a border."""
        return self._backend.hide_border(window_id)

    def hide_all_borders(self) -> None:
        """Hide all borders."""
        self._backend.hide_all_borders()

    def update_border_position(
        self,
        window_id: str,
        geometry: WindowGeometry
    ) -> bool:
        """Update a border's position."""
        return self._backend.update_border_position(window_id, geometry)
