"""CDP (Chrome DevTools Protocol) backend for browser automation on Wayland."""

import json
import subprocess
import time
import socket
import http.client
from typing import Optional, List, Dict, Any


class CDPClient:
    """Simple CDP client using HTTP + WebSocket-free approach (via /json endpoints)."""

    def __init__(self, host: str = "127.0.0.1", port: int = 9222):
        self.host = host
        self.port = port
        self._ws = None

    def _http_get(self, path: str) -> Any:
        """Make HTTP GET to CDP endpoint."""
        conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
        conn.request("GET", path)
        resp = conn.getresponse()
        data = resp.read().decode()
        conn.close()
        return json.loads(data)

    def _http_put(self, path: str, body: str = "") -> Any:
        conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
        conn.request("PUT", path, body)
        resp = conn.getresponse()
        data = resp.read().decode()
        conn.close()
        return json.loads(data) if data else {}

    def is_available(self) -> bool:
        """Check if CDP endpoint is reachable."""
        try:
            self._http_get("/json/version")
            return True
        except Exception:
            return False

    def list_targets(self) -> List[Dict]:
        """List all browser targets (tabs/pages)."""
        try:
            return self._http_get("/json/list")
        except Exception:
            return []

    def get_active_tab(self) -> Optional[Dict]:
        """Get the active/first page target."""
        targets = self.list_targets()
        pages = [t for t in targets if t.get("type") == "page"]
        return pages[0] if pages else None

    def new_tab(self, url: str = "about:blank") -> Optional[Dict]:
        """Open a new tab."""
        try:
            return self._http_put(f"/json/new?{url}")
        except Exception:
            return None

    def activate_tab(self, target_id: str) -> bool:
        """Activate a tab by target ID."""
        try:
            self._http_get(f"/json/activate/{target_id}")
            return True
        except Exception:
            return False

    def close_tab(self, target_id: str) -> bool:
        """Close a tab."""
        try:
            self._http_get(f"/json/close/{target_id}")
            return True
        except Exception:
            return False

    def _get_ws_url(self, target_id: Optional[str] = None) -> Optional[str]:
        """Get WebSocket URL for a target."""
        if target_id:
            targets = self.list_targets()
            tab = next((t for t in targets if t.get("id") == target_id), None)
        else:
            tab = self.get_active_tab()
        if not tab:
            return None
        return tab.get("webSocketDebuggerUrl")

    def navigate(self, url: str, target_id: Optional[str] = None) -> bool:
        """Navigate to URL via CDP."""
        ws_url = self._get_ws_url(target_id)
        if not ws_url:
            return False
        result = self._send_cdp_command(ws_url, "Page.navigate", {"url": url})
        return result is not None

    def evaluate(self, expression: str, target_id: Optional[str] = None) -> Any:
        """Evaluate JavaScript in page."""
        ws_url = self._get_ws_url(target_id)
        if not ws_url:
            return None
        return self._send_cdp_command(ws_url, "Runtime.evaluate", {"expression": expression})

    def click_element(self, selector: str) -> bool:
        """Click element by CSS selector."""
        js = f'document.querySelector("{selector}")?.click()'
        result = self.evaluate(js)
        return result is not None

    def type_in_element(self, selector: str, text: str) -> bool:
        """Type text into element."""
        # Focus + set value + dispatch events
        js = f'''
        (function() {{
            var el = document.querySelector("{selector}");
            if (!el) return false;
            el.focus();
            el.value = "{text}";
            el.dispatchEvent(new Event("input", {{bubbles: true}}));
            el.dispatchEvent(new Event("change", {{bubbles: true}}));
            return true;
        }})()
        '''
        result = self.evaluate(js)
        return result is not None

    def get_page_title(self) -> str:
        """Get current page title."""
        result = self.evaluate("document.title")
        if result and isinstance(result, dict):
            return result.get("result", {}).get("value", "")
        return ""

    def get_page_url(self) -> str:
        """Get current page URL."""
        result = self.evaluate("window.location.href")
        if result and isinstance(result, dict):
            return result.get("result", {}).get("value", "")
        return ""

    def _send_cdp_command(self, ws_url: str, method: str, params: dict = None) -> Any:
        """Send CDP command via WebSocket (minimal implementation)."""
        try:
            import websocket
            ws = websocket.create_connection(ws_url, timeout=10)
            msg = {"id": 1, "method": method, "params": params or {}}
            ws.send(json.dumps(msg))
            response = json.loads(ws.recv())
            ws.close()
            return response.get("result")
        except ImportError:
            return self._send_via_websocat(ws_url, method, params)
        except Exception as e:
            return None

    def _raw_cdp(self, method: str, params: dict = None) -> Any:
        """Send raw CDP command to active tab."""
        ws_url = self._get_ws_url()
        if not ws_url:
            return None
        return self._send_cdp_command(ws_url, method, params or {})

    def dispatch_mouse(self, x: int, y: int, click_type: str = "click"):
        """Simulate real mouse click at viewport coordinates."""
        self._raw_cdp("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1
        })
        time.sleep(0.05)
        self._raw_cdp("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1
        })

    def dispatch_key(self, text: str):
        """Simulate real keyboard typing character by character."""
        for ch in text:
            self._raw_cdp("Input.dispatchKeyEvent", {
                "type": "keyDown",
                "text": ch,
                "key": ch,
                "code": f"Key{ch.upper()}" if ch.isalpha() else "",
                "unmodifiedText": ch
            })
            time.sleep(0.02)
            self._raw_cdp("Input.dispatchKeyEvent", {
                "type": "keyUp",
                "key": ch
            })

    def type_text(self, selector: str = None, text: str = ""):
        """Type text using real keyboard events. If selector is provided, focus element first via JS."""
        if selector:
            # Focus element via JS, then dispatch key events to it
            self.evaluate(f'''
                (function() {{
                    const el = document.querySelector("{selector}");
                    if (el) {{
                        el.focus();
                        return true;
                    }}
                    return false;
                }})()
            ''')
            time.sleep(0.2)
        # Now dispatch key events one by one
        self.dispatch_key(text)

    def take_screenshot(self) -> Optional[str]:
        """Take a screenshot of the browser page, returns base64 PNG."""
        result = self._raw_cdp("Page.captureScreenshot", {"format": "png"})
        if result and isinstance(result, dict):
            return result.get("data")
        return None

    def _send_via_websocat(self, ws_url: str, method: str, params: dict = None) -> Any:
        """Fallback: use websocat CLI for WebSocket."""
        msg = json.dumps({"id": 1, "method": method, "params": params or {}})
        try:
            result = subprocess.run(
                ['websocat', '-1', ws_url],
                input=msg, capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout:
                return json.loads(result.stdout).get("result")
        except Exception:
            pass
        return None


def launch_chromium_with_cdp(port: int = 9222, url: str = "about:blank") -> subprocess.Popen:
    """Launch Chromium with remote debugging enabled."""
    # Try multiple browser names
    for browser in ['chromium-browser', 'chromium', 'google-chrome', 'google-chrome-stable']:
        try:
            proc = subprocess.Popen([
                browser,
                f'--remote-debugging-port={port}',
                '--remote-allow-origins=*',
                '--no-first-run',
                '--no-default-browser-check',
                url
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(3)  # Wait for browser to start
            return proc
        except FileNotFoundError:
            continue
    return None


def launch_firefox_with_marionette(port: int = 2828) -> subprocess.Popen:
    """Launch Firefox with Marionette enabled."""
    try:
        proc = subprocess.Popen([
            'firefox', '--marionette', f'--marionette-port={port}'
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
        return proc
    except FileNotFoundError:
        return None


def get_or_create_cdp_client(port: int = 9222) -> Optional[CDPClient]:
    """Get existing CDP connection or launch browser."""
    client = CDPClient(port=port)
    if client.is_available():
        return client
    # Try launching Chromium
    proc = launch_chromium_with_cdp(port=port)
    if proc:
        time.sleep(2)
        if client.is_available():
            return client
    return None
