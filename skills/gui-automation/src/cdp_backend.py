"""
CDP backend integration for GUI automation agent.
Provides click, type, navigate actions via Chrome DevTools Protocol.
"""

import time
from typing import Optional, Dict, Any

from .cdp_helper import CDPClient, get_or_create_cdp_client


class CDPBackend:
    """Backend for controlling Chromium/Chrome via CDP."""

    def __init__(self, port: int = 9222):
        self.client: Optional[CDPClient] = None
        self.port = port
        self._ensure_started()

    def _ensure_started(self):
        """Ensure a CDP-capable browser is running."""
        self.client = get_or_create_cdp_client(port=self.port)
        if not self.client:
            raise RuntimeError("Failed to start CDP browser")

    def navigate(self, url: str):
        """Navigate to URL."""
        return self.client.navigate(url)

    def click(self, x: int, y: int):
        """Click at coordinates via JavaScript (No native click via CDP without DOM)."""
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
        self.client.type_text(selector, text)
        return f"typed: '{text}' via dispatchKeyEvent"

    def press_key(self, key: str):
        """Press a key (e.g., 'Enter', 'Tab')."""
        self.client._raw_cdp("Input.dispatchKeyEvent", {"type": "keyDown", "key": key, "text": key})
        time.sleep(0.05)
        self.client._raw_cdp("Input.dispatchKeyEvent", {"type": "keyUp", "key": key})
        return f"pressed: {key}"

    def click_at(self, x: int, y: int):
        """Click at viewport coordinates via mouse dispatch."""
        self.client.dispatch_mouse(x, y)
        return f"clicked at ({x},{y})"

    def get_page_info(self) -> Dict[str, Any]:
        """Get current page URL and title."""
        return {
            "url": self.client.get_page_url(),
            "title": self.client.get_page_title()
        }

    def wait_for_load(self, timeout: float = 10.0):
        """Wait for page to load (simple polling)."""
        time.sleep(2)  # Basic wait; could improve with readyState check
        return True
