"""
Marionette backend integration for GUI automation agent.
Provides click, type, navigate actions via Firefox Marionette protocol.
"""

import time
from typing import Optional, Dict, Any

from .marionette_helper import MarionetteClient, get_or_create_marionette_client


class MarionetteBackend:
    """Backend for controlling Firefox via Marionette."""

    def __init__(self, port: int = 2828):
        self.client: Optional[MarionetteClient] = None
        self.port = port
        self._session_id = None
        self._ensure_started()

    def _ensure_started(self):
        """Ensure Firefox with Marionette is running."""
        self.client = get_or_create_marionette_client(port=self.port)
        if not self.client:
            raise RuntimeError("Failed to start Firefox with Marionette")
        self._session_id = self.client.new_session()

    def navigate(self, url: str):
        """Navigate to URL."""
        return self.client.navigate(url)

    def click_element(self, selector: str) -> bool:
        """Click element by CSS selector."""
        el = self.client.find_element("css selector", selector)
        if el:
            return self.client.click_element(el)
        return False

    def type_in_element(self, selector: str, text: str) -> str:
        """Type text into element by CSS selector."""
        el = self.client.find_element("css selector", selector)
        if el:
            self.client.send_keys(el, text)
            return f"typed: '{text}'"
        return "element not found"

    def press_key(self, key: str):
        """Press a key by sending to active element."""
        # Marionette uses WebDriver key codes
        key_map = {
            "Enter": "\ue007", "Tab": "\ue004", "Escape": "\ue00c",
            "ArrowUp": "\ue013", "ArrowDown": "\ue015",
            "ArrowLeft": "\ue012", "ArrowRight": "\ue014",
            "Backspace": "\ue003", "Delete": "\ue017",
        }
        char = key_map.get(key, key)
        # Send to active element
        self.client.execute_script(f"arguments[0].dispatchEvent(new KeyboardEvent('keydown', {{key: '{key}'}}));",
                                    ["document.activeElement"])
        return f"pressed: {key}"

    def get_page_info(self) -> Dict[str, Any]:
        """Get current page URL and title."""
        return {
            "url": self.client.get_url(),
            "title": self.client.get_title()
        }

    def take_screenshot(self) -> Optional[str]:
        """Take screenshot, returns base64 PNG."""
        return self.client.take_screenshot()

    def evaluate(self, script: str) -> Any:
        """Execute JavaScript."""
        return self.client.execute_script(script)

    def get_window_handles(self):
        """List all tabs/windows."""
        return self.client.get_window_handles()

    def switch_to_window(self, handle: str):
        """Switch to tab/window."""
        return self.client.switch_to_window(handle)

    def close_window(self):
        """Close current tab."""
        return self.client.close_window()
