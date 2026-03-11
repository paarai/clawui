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

    def type(self, text: str, target_selector: str = None):
        """
        Type text into focused element or a specific CSS selector.
        If no selector, assumes element already focused.
        """
        if target_selector:
            js = f'''
            (function() {{
                const el = document.querySelector("{target_selector}");
                if (!el) return "no-element";
                el.focus();
                el.value = "{text}";
                el.dispatchEvent(new Event('input', {{bubbles:true}}));
                el.dispatchEvent(new Event('change', {{bubbles:true}}));
                return "typed";
            }})()
            '''
            return self.client.evaluate(js)
        else:
            # Just simulate typing into active element
            js = f'''
            (function() {{
                const el = document.activeElement;
                if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {{
                    el.value += "{text}";
                    el.dispatchEvent(new Event('input', {{bubbles:true}}));
                    return "typed";
                }}
                return "no-input";
            }})()
            '''
            return self.client.evaluate(js)

    def press_key(self, key: str):
        """Press a key (e.g., 'Enter', 'Tab')."""
        key_map = {
            "Return": "Enter", "Escape": "Escape", "Tab": "Tab",
            "ArrowUp": "ArrowUp", "ArrowDown": "ArrowDown",
            "ArrowLeft": "ArrowLeft", "ArrowRight": "ArrowRight"
        }
        js_key = key_map.get(key, key)
        js = f'''
        (function() {{
            const ev = new KeyboardEvent('keydown', {{key: '{js_key}'}});
            document.activeElement.dispatchEvent(ev);
            return "pressed:" + '{js_key}';
        }})()
        '''
        return self.client.evaluate(js)

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
