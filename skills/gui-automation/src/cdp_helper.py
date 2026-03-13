"""CDP (Chrome DevTools Protocol) backend for browser automation on Wayland."""

import base64
import json
import os
import subprocess
import time
import socket
import http.client
from typing import Optional, List, Dict, Any

# Default persistent profile directory for auto-launched Chromium
DEFAULT_USER_DATA_DIR = os.path.join(
    os.path.expanduser("~"),
    ".local",
    "share",
    "clawui",
    "chromium_profile"
)


def ensure_gui_environment():
    """
    Ensure DISPLAY, WAYLAND_DISPLAY, and XAUTHORITY are set for GUI operations.
    Tries to detect the active graphical session and configure environment.
    """
    # If already have these, nothing to do
    if os.environ.get('DISPLAY') or (os.environ.get('WAYLAND_DISPLAY') and os.environ.get('XAUTHORITY')):
        return

    # Try to find DISPLAY from X11 sockets
    if not os.environ.get('DISPLAY'):
        for i in [0, 1]:
            if os.path.exists(f'/tmp/.X11-unix/X{i}'):
                os.environ['DISPLAY'] = f':{i}'
                print(f'[CDP] Auto-detected DISPLAY={":%d" % i}')
                break

    # Try to find WAYLAND_DISPLAY
    if not os.environ.get('WAYLAND_DISPLAY'):
        # Common Wayland socket in user runtime
        wayland_sock = '/run/user/1000/wayland-0'
        if os.path.exists(wayland_sock) or os.path.exists(wayland_sock.replace('1000', str(os.getuid()))):
            os.environ['WAYLAND_DISPLAY'] = 'wayland-0'
            print('[CDP] Auto-detected WAYLAND_DISPLAY=wayland-0')

    # Try to find XAUTHORITY
    if not os.environ.get('XAUTHORITY'):
        candidates = [
            os.path.expanduser('~/.Xauthority'),
            f'/run/user/{os.getuid()}/.mutter-Xwayland-0',
            f'/run/user/{os.getuid()}/.Xauthority',
        ]
        for path in candidates:
            if os.path.exists(path):
                os.environ['XAUTHORITY'] = path
                print(f'[CDP] Auto-detected XAUTHORITY={path}')
                break

    # If we have DISPLAY but no XAUTHORITY, try to generate one via xauth if available
    if os.environ.get('DISPLAY') and not os.environ.get('XAUTHORITY'):
        try:
            # Use the display we set to generate a new authority file
            import getpass
            home = os.path.expanduser('~')
            xauth_path = os.path.join(home, '.Xauthority')
            # Ensure directory exists
            os.makedirs(os.path.dirname(xauth_path), exist_ok=True)
            # Generate using xauth
            subprocess.run(['xauth', 'generate', os.environ['DISPLAY'], '.', 'trusted'], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(xauth_path):
                os.environ['XAUTHORITY'] = xauth_path
                print(f'[CDP] Generated new XAUTHORITY at {xauth_path}')
        except Exception:
            pass

# Call it at module import to configure environment
ensure_gui_environment()


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
            conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
            conn.request("GET", f"/json/activate/{target_id}")
            resp = conn.getresponse()
            resp.read()
            conn.close()
            return resp.status == 200
        except Exception:
            return False

    def close_tab(self, target_id: str) -> bool:
        """Close a tab."""
        try:
            conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
            conn.request("GET", f"/json/close/{target_id}")
            resp = conn.getresponse()
            resp.read()
            conn.close()
            return resp.status == 200
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
        """Type text using real keyboard events. If selector provided, click+focus first."""
        if selector:
            self.evaluate(f'''
                (function() {{
                    const el = document.querySelector("{selector}");
                    if (el) {{ el.click(); el.focus(); return true; }}
                    return false;
                }})()
            ''')
            time.sleep(0.3)
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


# Global registry to keep launched browser processes alive
_launched_browser_processes = {}


def launch_chromium_with_cdp(port: int = 9222, url: str = "about:blank") -> Optional[subprocess.Popen]:
    """Launch Chromium/Chrome with remote debugging enabled.

    Tries multiple detection strategies in order:
    1. Common binary names in PATH (chromium-browser, chromium, google-chrome, google-chrome-stable, chrome)
    2. Snap installations (snap run chromium)
    3. Flatpak installations (flatpak run org.chromium.Chromium)
    4. Headless variants (for environments without DISPLAY)
    5. Try with --no-sandbox for restricted environments (snap)

    Returns the Popen object if successful, None otherwise.
    """
    # Ensure the persistent profile directory exists
    os.makedirs(DEFAULT_USER_DATA_DIR, exist_ok=True)

    # Base arguments common to all launches
    base_args = [
        f'--remote-debugging-port={port}',
        '--remote-allow-origins=*',
        '--no-first-run',
        '--no-default-browser-check',
        f'--user-data-dir={DEFAULT_USER_DATA_DIR}',
        url
    ]

    # Candidate commands grouped by strategy
    candidates = [
        # Direct binaries in PATH (with display)
        ['chromium-browser'] + base_args,
        ['chromium'] + base_args,
        ['google-chrome'] + base_args,
        ['google-chrome-stable'] + base_args,
        ['chrome'] + base_args,
        # Snap
        ['snap', 'run', 'chromium'] + base_args,
        # Flatpak
        ['flatpak', 'run', 'org.chromium.Chromium'] + base_args,
        # Headless variants (for headless/cron environments)
        ['chromium-browser', '--headless=new'] + base_args,
        ['chromium', '--headless=new'] + base_args,
        ['google-chrome', '--headless=new'] + base_args,
        ['google-chrome-stable', '--headless=new'] + base_args,
        ['chrome', '--headless=new'] + base_args,
        # Snap headless
        ['snap', 'run', 'chromium', '--headless=new'] + base_args,
        # With --no-sandbox (for snap confinement issues)
        ['snap', 'run', 'chromium', '--no-sandbox'] + base_args,
        ['chromium-browser', '--no-sandbox'] + base_args,
    ]

    for cmd in candidates:
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Wait a bit for browser to start and open CDP endpoint
            time.sleep(3)
            if _is_port_listening(port):
                _launched_browser_processes[port] = proc
                return proc
            else:
                # Port not open yet, wait a bit more
                time.sleep(2)
                if _is_port_listening(port):
                    _launched_browser_processes[port] = proc
                    return proc
                # Not ready, terminate and try next
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except:
                    pass
        except FileNotFoundError:
            continue
        except Exception:
            continue

    return None


def _is_port_listening(port: int, host: str = "127.0.0.1") -> bool:
    """Check if something is listening on the given port."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False


def get_or_create_cdp_client(port: int = 9222) -> Optional[CDPClient]:
    """Get existing CDP connection or launch a browser automatically.

    If a browser is already running with CDP on the specified port, returns a client.
    Otherwise, attempts to launch a suitable browser and returns a client connected to it.
    """
    client = CDPClient(port=port)
    if client.is_available():
        return client

    # Try to launch a browser
    proc = launch_chromium_with_cdp(port=port)
    if proc:
        # Wait a moment for CDP to be ready
        time.sleep(2)
        if client.is_available():
            return client
        # Additional wait if needed
        time.sleep(2)
        if client.is_available():
            return client

    return None


def get_browser_process(port: int = 9222) -> Optional[subprocess.Popen]:
    """Get the Popen object for a browser launched by this module (if any)."""
    return _launched_browser_processes.get(port)

