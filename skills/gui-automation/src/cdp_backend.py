"""
CDP backend integration for GUI automation agent.
Provides click, type, navigate actions via Chrome DevTools Protocol.
Includes automatic reconnection for improved reliability.
"""

import time
import random
from typing import Optional, Dict, Any

from .cdp_helper import CDPClient, get_or_create_cdp_client


class CDPBackend:
    """Backend for controlling Chromium/Chrome via CDP with automatic reconnection."""

    def __init__(self, port: int = 9222):
        self.client: Optional[CDPClient] = None
        self.port = port
        self._max_reconnect_attempts = 3
        self._reconnect_base_delay = 1.0
        self._ensure_started()

    def _ensure_connection(self):
        """Ensure the CDP connection is healthy; reconnect if lost."""
        if self.client is None:
            self._reconnect()

        for attempt in range(self._max_reconnect_attempts):
            try:
                # Quick health check: is endpoint reachable and responsive?
                if self.client and self.client.is_available():
                    self.client.list_targets()  # cheap probe
                    return
            except Exception:
                pass
            # Connection failed, attempt reconnection
            self._reconnect(attempt)

        raise RuntimeError(f"CDP connection lost after {self._max_reconnect_attempts} reconnection attempts")

    def _reconnect(self, attempt: int = 0):
        """Attempt to obtain a fresh CDP client, launching browser if needed."""
        delay = self._reconnect_base_delay * (2 ** attempt) + random.uniform(0, 0.5)
        time.sleep(delay)
        self.client = get_or_create_cdp_client(port=self.port)
        if not self.client:
            raise RuntimeError("Failed to (re)connect to CDP browser")

    def _ensure_started(self):
        """Ensure a CDP-capable browser is running (with retry)."""
        for attempt in range(self._max_reconnect_attempts):
            try:
                self.client = get_or_create_cdp_client(port=self.port)
                if self.client:
                    return
            except Exception:
                pass
            if attempt < self._max_reconnect_attempts - 1:
                time.sleep(self._reconnect_base_delay * (2 ** attempt) + random.uniform(0, 0.5))
        raise RuntimeError("Failed to start CDP browser after retries")

    def navigate(self, url: str):
        """Navigate to URL."""
        self._ensure_connection()
        return self.client.navigate(url)

    def click(self, x: int, y: int):
        """Click at coordinates via JavaScript (No native click via CDP without DOM)."""
        self._ensure_connection()
        # We use JavaScript to dispatch a mouse event at (x,y)
        js = f'''
        (function() {{
            const el = document.elementFromPoint({x}, {y});
            if (el) {{
                const rect = el.getBoundingClientRect();
                const ev = new MouseEvent('click', {{
                    view: window,
                    bubbles: true,
                    cancelable: true,
                    clientX: {x},
                    clientY: {y}
                }});
                el.dispatchEvent(ev);
                return "clicked:" + el.tagName;
            }}
            return "no-element";
        }})()
        '''
        return self.client.evaluate(js)

    def type_in_element(self, text: str, selector: str = None):
        """Type text using real keyboard dispatch (robust)."""
        self._ensure_connection()
        self.client.type_text(selector, text)
        return f"typed: '{text}' via dispatchKeyEvent"

    def press_key(self, key: str):
        """Press a key (e.g., 'Enter', 'Tab')."""
        self._ensure_connection()
        self.client._raw_cdp("Input.dispatchKeyEvent", {"type": "keyDown", "key": key, "text": key})
        time.sleep(0.05)
        self.client._raw_cdp("Input.dispatchKeyEvent", {"type": "keyUp", "key": key})
        return f"pressed: {key}"

    def click_at(self, x: int, y: int):
        """Click at viewport coordinates via mouse dispatch."""
        self._ensure_connection()
        self.client.dispatch_mouse(x, y)
        return f"clicked at ({x},{y})"

    def get_page_info(self) -> Dict[str, Any]:
        """Get current page URL and title."""
        self._ensure_connection()
        return {
            "url": self.client.get_page_url(),
            "title": self.client.get_page_title()
        }

    def wait_for_load(self, timeout: float = 10.0):
        """Wait for page to load (simple polling)."""
        self._ensure_connection()
        time.sleep(2)  # Basic wait; could improve with readyState check
        return True
