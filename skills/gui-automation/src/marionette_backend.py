"""
Marionette backend integration for GUI automation agent.
Provides click, type, navigate actions via Firefox Marionette protocol.
Includes automatic reconnection and session recovery for reliability.
"""

import time
import random
from typing import Optional, Dict, Any, List

from .marionette_helper import MarionetteClient, get_or_create_marionette_client


class MarionetteBackend:
    """Backend for controlling Firefox via Marionette with auto-reconnect."""

    def __init__(self, port: int = 2828):
        self.client: Optional[MarionetteClient] = None
        self.port = port
        self._session_id: Optional[str] = None
        self._max_reconnect_attempts = 3
        self._reconnect_base_delay = 1.0
        self._ensure_started()

    def _ensure_connection(self):
        """Ensure the Marionette connection and session are healthy; reconnect if lost."""
        if self.client is None:
            self._reconnect()

        for attempt in range(self._max_reconnect_attempts):
            try:
                # Perform a lightweight RPC to verify connection and session.
                # Using get_title() is safe and cheap.
                title = self.client.get_title()
                # Even an empty title indicates a working session.
                return
            except Exception:
                pass
            # Something failed, attempt reconnection (which recreates session)
            self._reconnect(attempt)

        raise RuntimeError(f"Marionette connection lost after {self._max_reconnect_attempts} reconnection attempts")

    def _reconnect(self, attempt: int = 0):
        """Close existing connection (if any) and create fresh client + session."""
        # Close old connection
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None
            self._session_id = None

        delay = self._reconnect_base_delay * (2 ** attempt) + random.uniform(0, 0.5)
        time.sleep(delay)

        self.client = get_or_create_marionette_client(port=self.port)
        if not self.client:
            raise RuntimeError("Failed to connect to Marionette")

        # Create a new session
        self._session_id = self.client.new_session()
        if not self._session_id:
            # New session failed, but client may still be usable? Consider it unhealthy.
            raise RuntimeError("Failed to create Marionette session")

    def _ensure_started(self):
        """Ensure Firefox with Marionette is running and session created (with retry)."""
        for attempt in range(self._max_reconnect_attempts):
            try:
                self.client = get_or_create_marionette_client(port=self.port)
                if not self.client:
                    continue
                self._session_id = self.client.new_session()
                if self._session_id:
                    return
            except Exception:
                pass
            if attempt < self._max_reconnect_attempts - 1:
                time.sleep(self._reconnect_base_delay * (2 ** attempt) + random.uniform(0, 0.5))
        raise RuntimeError("Failed to start Marionette browser after retries")

    def navigate(self, url: str):
        """Navigate to URL."""
        self._ensure_connection()
        return self.client.navigate(url)

    def click_element(self, selector: str) -> bool:
        """Click element by CSS selector."""
        self._ensure_connection()
        el = self.client.find_element("css selector", selector)
        if el:
            return self.client.click_element(el)
        return False

    def type_in_element(self, selector: str, text: str) -> str:
        """Type text into element by CSS selector."""
        self._ensure_connection()
        el = self.client.find_element("css selector", selector)
        if el:
            self.client.send_keys(el, text)
            return f"typed: '{text}'"
        return "element not found"

    def press_key(self, key: str):
        """Press a key by sending to active element."""
        self._ensure_connection()
        # Marionette uses WebDriver key codes
        key_map = {
            "Enter": "\ue007", "Tab": "\ue004", "Escape": "\ue00c",
            "ArrowUp": "\ue013", "ArrowDown": "\ue015",
            "ArrowLeft": "\ue012", "ArrowRight": "\ue014",
            "Backspace": "\ue003", "Delete": "\ue017",
        }
        char = key_map.get(key, key)
        # Send to active element
        self.client.execute_script(
            f"arguments[0].dispatchEvent(new KeyboardEvent('keydown', {{key: '{key}'}}));",
            ["document.activeElement"]
        )
        return f"pressed: {key}"

    def get_page_info(self) -> Dict[str, Any]:
        """Get current page URL and title."""
        self._ensure_connection()
        return {
            "url": self.client.get_url(),
            "title": self.client.get_title()
        }

    def take_screenshot(self) -> Optional[str]:
        """Take screenshot, returns base64 PNG."""
        self._ensure_connection()
        return self.client.take_screenshot()

    def evaluate(self, script: str) -> Any:
        """Execute JavaScript."""
        self._ensure_connection()
        return self.client.execute_script(script)

    def get_window_handles(self) -> List[str]:
        """List all tabs/windows."""
        self._ensure_connection()
        return self.client.get_window_handles()

    def switch_to_window(self, handle: str):
        """Switch to tab/window."""
        self._ensure_connection()
        return self.client.switch_to_window(handle)

    def close_window(self):
        """Close current tab."""
        self._ensure_connection()
        return self.client.close_window()
