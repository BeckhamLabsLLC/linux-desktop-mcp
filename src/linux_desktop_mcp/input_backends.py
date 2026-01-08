"""Input simulation backends for different display servers.

Provides abstracted input methods that work across X11, Wayland, and XWayland.
Priority: AT-SPI input > ydotool > xdotool
"""

import asyncio
import subprocess
import shutil
from abc import ABC, abstractmethod
from typing import Optional
import logging

from .detection import DisplayServer, PlatformCapabilities, detect_capabilities
from .references import ElementReference

logger = logging.getLogger(__name__)

# Input validation constants
MAX_TEXT_LENGTH = 10000


class InputBackend(ABC):
    """Abstract base class for input simulation backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend name."""
        pass

    @abstractmethod
    async def click(
        self,
        x: int,
        y: int,
        button: str = "left",
        click_type: str = "single",
        modifiers: Optional[list[str]] = None
    ) -> bool:
        """Perform a mouse click at coordinates.

        Args:
            x: X coordinate.
            y: Y coordinate.
            button: "left", "right", or "middle".
            click_type: "single" or "double".
            modifiers: List of modifiers like ["ctrl", "shift"].

        Returns:
            True if click succeeded.
        """
        pass

    @abstractmethod
    async def type_text(self, text: str, delay_ms: int = 12) -> bool:
        """Type text using keyboard simulation.

        Args:
            text: Text to type.
            delay_ms: Delay between keystrokes in milliseconds.

        Returns:
            True if typing succeeded.
        """
        pass

    @abstractmethod
    async def key(self, key: str, modifiers: Optional[list[str]] = None) -> bool:
        """Press a key with optional modifiers.

        Args:
            key: Key name (e.g., "Return", "Tab", "a").
            modifiers: List of modifiers like ["ctrl", "shift"].

        Returns:
            True if key press succeeded.
        """
        pass

    @abstractmethod
    async def move(self, x: int, y: int) -> bool:
        """Move mouse to coordinates.

        Args:
            x: X coordinate.
            y: Y coordinate.

        Returns:
            True if move succeeded.
        """
        pass


class YdotoolBackend(InputBackend):
    """Input backend using ydotool (works on Wayland and X11)."""

    BUTTON_MAP = {"left": 0x110, "right": 0x111, "middle": 0x112}

    @property
    def name(self) -> str:
        return "ydotool"

    async def _run(self, *args) -> bool:
        """Run ydotool command."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ydotool", *args,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error(f"ydotool error: {stderr.decode()}")
                return False
            return True
        except Exception as e:
            logger.error(f"ydotool failed: {e}")
            return False

    async def click(
        self,
        x: int,
        y: int,
        button: str = "left",
        click_type: str = "single",
        modifiers: Optional[list[str]] = None
    ) -> bool:
        await self.move(x, y)
        await asyncio.sleep(0.05)

        button_code = self.BUTTON_MAP.get(button, 0x110)
        clicks = 2 if click_type == "double" else 1

        for _ in range(clicks):
            if not await self._run("click", hex(button_code)):
                return False
            if click_type == "double":
                await asyncio.sleep(0.05)

        return True

    async def type_text(self, text: str, delay_ms: int = 12) -> bool:
        return await self._run("type", "--delay", str(delay_ms), "--", text)

    async def key(self, key: str, modifiers: Optional[list[str]] = None) -> bool:
        key_sequence = key
        if modifiers:
            mod_str = "+".join(modifiers)
            key_sequence = f"{mod_str}+{key}"

        return await self._run("key", key_sequence)

    async def move(self, x: int, y: int) -> bool:
        return await self._run("mousemove", "--absolute", str(x), str(y))


class XdotoolBackend(InputBackend):
    """Input backend using xdotool (X11 only)."""

    BUTTON_MAP = {"left": "1", "right": "3", "middle": "2"}

    @property
    def name(self) -> str:
        return "xdotool"

    async def _run(self, *args) -> bool:
        """Run xdotool command."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "xdotool", *args,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error(f"xdotool error: {stderr.decode()}")
                return False
            return True
        except Exception as e:
            logger.error(f"xdotool failed: {e}")
            return False

    async def click(
        self,
        x: int,
        y: int,
        button: str = "left",
        click_type: str = "single",
        modifiers: Optional[list[str]] = None
    ) -> bool:
        button_num = self.BUTTON_MAP.get(button, "1")

        args = ["mousemove", str(x), str(y)]
        if not await self._run(*args):
            return False

        await asyncio.sleep(0.05)

        click_cmd = "click"
        if click_type == "double":
            click_cmd = "click"
            args = [click_cmd, "--repeat", "2", "--delay", "50", button_num]
        else:
            args = [click_cmd, button_num]

        return await self._run(*args)

    async def type_text(self, text: str, delay_ms: int = 12) -> bool:
        return await self._run("type", "--delay", str(delay_ms), "--", text)

    async def key(self, key: str, modifiers: Optional[list[str]] = None) -> bool:
        key_sequence = key
        if modifiers:
            mod_str = "+".join(modifiers)
            key_sequence = f"{mod_str}+{key}"

        return await self._run("key", key_sequence)

    async def move(self, x: int, y: int) -> bool:
        return await self._run("mousemove", str(x), str(y))


class WtypeBackend(InputBackend):
    """Input backend using wtype (Wayland keyboard only)."""

    @property
    def name(self) -> str:
        return "wtype"

    async def _run(self, *args) -> bool:
        """Run wtype command."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "wtype", *args,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error(f"wtype error: {stderr.decode()}")
                return False
            return True
        except Exception as e:
            logger.error(f"wtype failed: {e}")
            return False

    async def click(
        self,
        x: int,
        y: int,
        button: str = "left",
        click_type: str = "single",
        modifiers: Optional[list[str]] = None
    ) -> bool:
        logger.warning("wtype does not support mouse clicks")
        return False

    async def type_text(self, text: str, delay_ms: int = 12) -> bool:
        return await self._run("-d", str(delay_ms), text)

    async def key(self, key: str, modifiers: Optional[list[str]] = None) -> bool:
        args = []
        if modifiers:
            for mod in modifiers:
                args.extend(["-M", mod])

        args.extend(["-k", key])

        if modifiers:
            for mod in reversed(modifiers):
                args.extend(["-m", mod])

        return await self._run(*args)

    async def move(self, x: int, y: int) -> bool:
        logger.warning("wtype does not support mouse movement")
        return False


class InputManager:
    """Manages input backends and provides unified input interface.

    Automatically selects the best available backend based on platform
    capabilities and display server.
    """

    def __init__(self, capabilities: Optional[PlatformCapabilities] = None):
        self._capabilities = capabilities or detect_capabilities()
        self._backend: Optional[InputBackend] = None
        self._keyboard_backend: Optional[InputBackend] = None
        self._initialize_backends()

    def _initialize_backends(self):
        """Initialize the best available backends."""
        caps = self._capabilities

        if caps.display_server == DisplayServer.WAYLAND:
            if caps.has_ydotool:
                self._backend = YdotoolBackend()
                self._keyboard_backend = self._backend
            elif caps.has_wtype:
                self._keyboard_backend = WtypeBackend()
                logger.warning("Only keyboard input available (wtype). Mouse input requires ydotool.")
        else:
            if caps.has_xdotool:
                self._backend = XdotoolBackend()
                self._keyboard_backend = self._backend
            elif caps.has_ydotool:
                self._backend = YdotoolBackend()
                self._keyboard_backend = self._backend

        if self._backend:
            logger.info(f"Using input backend: {self._backend.name}")
        else:
            logger.warning("No mouse input backend available")

        if self._keyboard_backend and self._keyboard_backend != self._backend:
            logger.info(f"Using keyboard backend: {self._keyboard_backend.name}")

    @property
    def backend_name(self) -> Optional[str]:
        """Get the name of the active backend."""
        return self._backend.name if self._backend else None

    @property
    def can_click(self) -> bool:
        """Check if mouse clicks are supported."""
        return self._backend is not None

    @property
    def can_type(self) -> bool:
        """Check if keyboard input is supported."""
        return self._keyboard_backend is not None

    async def click(
        self,
        x: int,
        y: int,
        button: str = "left",
        click_type: str = "single",
        modifiers: Optional[list[str]] = None
    ) -> bool:
        """Perform a mouse click."""
        if not self._backend:
            logger.error("No input backend available for mouse clicks")
            return False

        return await self._backend.click(x, y, button, click_type, modifiers)

    async def click_element(
        self,
        ref: ElementReference,
        button: str = "left",
        click_type: str = "single",
        modifiers: Optional[list[str]] = None
    ) -> bool:
        """Click an element by reference."""
        if not ref.bounds.is_valid:
            logger.error(f"Element {ref.ref_id} has invalid bounds")
            return False

        x, y = ref.bounds.center
        return await self.click(x, y, button, click_type, modifiers)

    async def type_text(self, text: str, delay_ms: int = 12) -> bool:
        """Type text."""
        if not self._keyboard_backend:
            logger.error("No keyboard backend available")
            return False

        if len(text) > MAX_TEXT_LENGTH:
            logger.error(f"Text too long: {len(text)} > {MAX_TEXT_LENGTH}")
            return False

        return await self._keyboard_backend.type_text(text, delay_ms)

    async def key(self, key: str, modifiers: Optional[list[str]] = None) -> bool:
        """Press a key."""
        if not self._keyboard_backend:
            logger.error("No keyboard backend available")
            return False

        return await self._keyboard_backend.key(key, modifiers)

    async def move(self, x: int, y: int) -> bool:
        """Move mouse to coordinates."""
        if not self._backend:
            logger.error("No input backend available for mouse movement")
            return False

        return await self._backend.move(x, y)

    async def clear_and_type(
        self,
        ref: ElementReference,
        text: str,
        delay_ms: int = 12
    ) -> bool:
        """Click element, clear it, and type new text."""
        if not await self.click_element(ref):
            return False

        await asyncio.sleep(0.1)

        if not await self.key("a", ["ctrl"]):
            return False

        await asyncio.sleep(0.05)

        if not await self.key("Delete"):
            return False

        await asyncio.sleep(0.05)

        return await self.type_text(text, delay_ms)

    async def type_and_submit(
        self,
        ref: ElementReference,
        text: str,
        delay_ms: int = 12
    ) -> bool:
        """Click element, type text, and press Enter."""
        if not await self.click_element(ref):
            return False

        await asyncio.sleep(0.1)

        if not await self.type_text(text, delay_ms):
            return False

        await asyncio.sleep(0.05)

        return await self.key("Return")
