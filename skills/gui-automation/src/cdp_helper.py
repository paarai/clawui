"""CDP (Chrome DevTools Protocol) backend for browser automation on Wayland."""

import base64
import json
import os
import subprocess
import sys
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


def inherit_gui_session_env():
    """
    Try to inherit GUI environment variables from the user's graphical session.
    Looks for processes like gnome-session, Xorg, or wayland and reads their /proc/PID/environ.
    """
    if os.environ.get('DISPLAY') and os.environ.get('XAUTHORITY'):
        # Already have what we need
        return

    # Find candidate processes that are likely running in the GUI session
    candidates = []
    try:
        # Find gnome-session processes owned by the current user
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if any(proc in line for proc in ['gnome-session', 'Xorg', 'wayland', 'gnome-shell']):
                parts = line.split()
                if len(parts) >= 2:
                    uid = parts[1]
                    if uid == str(os.getuid()):  # Owned by current user
                        pid = parts[1] if parts[1].isdigit() else None
                        if pid:
                            candidates.append(pid)
    except Exception:
        pass

    # Also try loginctl to find the graphical session
    try:
        sessions = subprocess.run(['loginctl', 'list-sessions', '--no-legend'], capture_output=True, text=True)
        for line in sessions.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[2] == 'user':
                sid = parts[0]
                info = subprocess.run(['loginctl', 'show-session', sid, '-p', 'Display', '-p', 'Type', '-p', 'Leader'], capture_output=True, text=True)
                leader = None
                display = None
                for l in info.stdout.splitlines():
                    if l.startswith('Leader='):
                        leader = l.split('=')[1]
                    elif l.startswith('Display='):
                        display = l.split('=')[1]
                if leader and leader.isdigit() and str(os.getuid()) == subprocess.run(['ps', '-o', 'uid=', '-p', leader], capture_output=True, text=True).stdout.strip():
                    candidates.append(leader)
                    if display and not os.environ.get('DISPLAY'):
                        os.environ['DISPLAY'] = display
                        print(f'[CDP] Inherited DISPLAY={display} from session leader {leader}')
    except Exception:
        pass

    # Read environment from candidate processes
    for pid in candidates:
        try:
            environ_path = f'/proc/{pid}/environ'
            if not os.path.exists(environ_path):
                continue
            with open(environ_path, 'rb') as f:
                data = f.read().split(b'\x00')
                env = {}
                for item in data:
                    if b'=' in item:
                        k, v = item.split(b'=', 1)
                        env[k.decode('utf-8', 'ignore')] = v.decode('utf-8', 'ignore')
                
                # Apply relevant variables
                for key in ['DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', ' WAYLAND_SOCKET']:
                    if key in env and not os.environ.get(key):
                        os.environ[key] = env[key]
                        print(f'[CDP] Inherited {key}={env[key]} from PID {pid}')
        except Exception:
            continue

    # Also try to set DBUS_SESSION_BUS_ADDRESS from the session
    try:
        dbus_addr = subprocess.run(['dbus-send', '--session', '--print-reply', '--dest=org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus.GetId'], capture_output=True, text=True, timeout=2)
        # Not reliable, skip
    except Exception:
        pass


def _running_interactively() -> bool:
    """Check if we appear to be running in an interactive session.
    Cron jobs and systemd services usually have no TTY.
    """
    # Check for common TTY indicators
    if sys.stdin.isatty():
        return True
    # SSH sessions often set SSH_TTY
    if os.environ.get('SSH_TTY'):
        return True
    # If TERM is set but not 'dumb' and we have a controlling TTY? Not foolproof.
    # Simpler: if DISPLAY/WAYLAND_DISPLAY already set, assume user intended GUI
    if os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'):
        return True
    return False

def ensure_gui_environment():
    """
    Ensure DISPLAY, WAYLAND_DISPLAY, and XAUTHORITY are set for GUI operations.
    Tries to detect the active graphical session and configure environment.
    Will skip auto-detection if running non-interactively (e.g., cron).
    """
    # If already have these, nothing to do
    if os.environ.get('DISPLAY') and os.environ.get('XAUTHORITY'):
        return

    # Skip auto-detection in non-interactive sessions (e.g., cron)
    if not _running_interactively():
        return

    # First, try to inherit from a running GUI session process
    inherit_gui_session_env()

    # If we still don't have DISPLAY, try fallback heuristics
    if not os.environ.get('DISPLAY'):
        for i in [0, 1]:
            if os.path.exists(f'/tmp/.X11-unix/X{i}'):
                os.environ['DISPLAY'] = f':{i}'
                print(f'[CDP] Auto-detected DISPLAY={":%d" % i}')
                break

    if not os.environ.get('WAYLAND_DISPLAY'):
        wayland_sock = f'/run/user/{os.getuid()}/wayland-0'
        if os.path.exists(wayland_sock):
            os.environ['WAYLAND_DISPLAY'] = 'wayland-0'
            print('[CDP] Auto-detected WAYLAND_DISPLAY=wayland-0')

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


def _xauthority_valid(path: Optional[str]) -> bool:
    """Check if Xauthority file exists and has non-trivial size."""
    if not path:
        return False
    try:
        return os.path.getsize(path) > 10
    except:
        return False

def launch_chromium_with_cdp(port: int = 9222, url: str = "about:blank") -> Optional[subprocess.Popen]:
    """Launch Chromium/Chrome with remote debugging enabled.

    Tries multiple detection strategies in order:
    1. Common binary names in PATH (chromium-browser, chromium, google-chrome, google-chrome-stable, chrome)
    2. Snap installations (snap run chromium)
    3. Flatpak installations (flatpak run org.chromium.Chromium)
    4. Headless variants (for environments without DISPLAY or with invalid XAUTHORITY)
    5. Try with --no-sandbox for restricted environments (snap)

    Returns the Popen object if successful, None otherwise.
    """
    # Ensure the persistent profile directory exists
    os.makedirs(DEFAULT_USER_DATA_DIR, exist_ok=True)

    # Determine if we can use headful mode (requires valid XAUTHORITY)
    xauth_valid = _xauthority_valid(os.environ.get('XAUTHORITY'))
    has_display = bool(os.environ.get('DISPLAY'))

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
    candidates = []

    # If we have a valid Xauthority and DISPLAY, try headful first
    if has_display and xauth_valid:
        candidates += [
            ['chromium-browser'] + base_args,
            ['chromium'] + base_args,
            ['google-chrome'] + base_args,
            ['google-chrome-stable'] + base_args,
            ['chrome'] + base_args,
            ['snap', 'run', 'chromium'] + base_args,
            ['flatpak', 'run', 'org.chromium.Chromium'] + base_args,
        ]

    # Always try headless (works without X)
    headless_base = ['--headless=new']
    candidates += [
        ['chromium-browser'] + headless_base + base_args,
        ['chromium'] + headless_base + base_args,
        ['google-chrome'] + headless_base + base_args,
        ['google-chrome-stable'] + headless_base + base_args,
        ['chrome'] + headless_base + base_args,
        ['snap', 'run', 'chromium'] + headless_base + base_args,
        # With --no-sandbox (for snap confinement issues)
        ['snap', 'run', 'chromium', '--no-sandbox'] + headless_base + base_args,
        ['chromium-browser', '--no-sandbox'] + headless_base + base_args,
    ]

    # Try fallback: non-headless with --no-sandbox (last resort)
    if not xauth_valid:
        candidates += [
            ['snap', 'run', 'chromium', '--no-sandbox'] + base_args,
            ['chromium-browser', '--no-sandbox'] + base_args,
        ]

    for cmd in candidates:
        try:
            # Start browser in its own process group to avoid being killed when parent exits
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True  # Create new session, detach from parent
            )
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

