"""CDP (Chrome DevTools Protocol) backend for browser automation on Wayland."""

import json
import os
import subprocess
import time
import socket
import http.client
import tempfile
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger("clawui.cdp_helper")

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
    # Use numeric UID output to avoid username/UID mismatch bugs in `ps aux` parsing.
    candidates = []
    try:
        result = subprocess.run(
            ['ps', '-eo', 'pid=,uid=,comm='],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in result.stdout.splitlines():
            parts = line.strip().split(None, 2)
            if len(parts) < 3:
                continue
            pid, uid, comm = parts
            if uid != str(os.getuid()):
                continue
            if any(proc in comm for proc in ['gnome-session', 'Xorg', 'wayland', 'gnome-shell']):
                if pid.isdigit():
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
                for line in info.stdout.splitlines():
                    if line.startswith('Leader='):
                        leader = line.split('=')[1]
                    elif line.startswith('Display='):
                        display = line.split('=')[1]
                if leader and leader.isdigit() and str(os.getuid()) == subprocess.run(['ps', '-o', 'uid=', '-p', leader], capture_output=True, text=True).stdout.strip():
                    candidates.append(leader)
                    if display and not os.environ.get('DISPLAY'):
                        os.environ['DISPLAY'] = display
                        logger.info('Inherited DISPLAY=%s from session leader %s', display, leader)
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
                for key in ['DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'WAYLAND_SOCKET']:
                    if key in env and not os.environ.get(key):
                        os.environ[key] = env[key]
                        logger.debug('Inherited %s=%s from PID %s', key, env[key], pid)
        except Exception:
            continue

    # Also try to set DBUS_SESSION_BUS_ADDRESS from the session
    try:
        subprocess.run(['dbus-send', '--session', '--print-reply', '--dest=org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus.GetId'], capture_output=True, text=True, timeout=2)
        # Not reliable, skip
    except Exception:
        pass



def ensure_gui_environment():
    """
    Ensure DISPLAY, WAYLAND_DISPLAY, and XAUTHORITY are set for GUI operations.
    Tries to detect the active graphical session and configure environment.
    Runs in both interactive and non-interactive sessions (cron).
    """
    # If already have these, nothing to do
    if os.environ.get('DISPLAY') and os.environ.get('XAUTHORITY'):
        return

    # Always attempt to detect GUI environment, even in non-interactive sessions
    # (e.g., cron). This is critical for reliable browser automation in scheduled tasks.
    inherit_gui_session_env()

    # If we still don't have DISPLAY, try fallback heuristics
    if not os.environ.get('DISPLAY'):
        for i in [0, 1]:
            if os.path.exists(f'/tmp/.X11-unix/X{i}'):
                os.environ['DISPLAY'] = f':{i}'
                logger.info('Auto-detected DISPLAY=:%d', i)
                break

    if not os.environ.get('WAYLAND_DISPLAY'):
        wayland_sock = f'/run/user/{os.getuid()}/wayland-0'
        if os.path.exists(wayland_sock):
            os.environ['WAYLAND_DISPLAY'] = 'wayland-0'
            logger.info('Auto-detected WAYLAND_DISPLAY=wayland-0')

    if not os.environ.get('XAUTHORITY'):
        candidates = [
            os.path.expanduser('~/.Xauthority'),
            f'/run/user/{os.getuid()}/.mutter-Xwayland-0',
            f'/run/user/{os.getuid()}/.Xauthority',
        ]
        for path in candidates:
            if os.path.exists(path):
                os.environ['XAUTHORITY'] = path
                logger.info('Auto-detected XAUTHORITY=%s', path)
                break

# Call it at module import to configure environment
ensure_gui_environment()


class CDPClient:
    """CDP client with persistent WebSocket connection for fast command execution."""

    def __init__(self, host: str = "127.0.0.1", port: int = 9222):
        self.host = host
        self.port = port
        self._ws = None
        self._ws_url = None
        self._ws_target_id = None
        self._msg_id = 0

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
            logger.debug("CDP endpoint reachable at %s:%s", self.host, self.port)
            return True
        except Exception:
            logger.debug("CDP endpoint not reachable at %s:%s", self.host, self.port)
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
        if not self._ensure_ws(target_id):
            return False
        result = self._send_cdp_command(self._ws_url, "Page.navigate", {"url": url})
        return result is not None

    def evaluate(self, expression: str, target_id: Optional[str] = None) -> Any:
        """Evaluate JavaScript in page."""
        if not self._ensure_ws(target_id):
            return None
        return self._send_cdp_command(self._ws_url, "Runtime.evaluate", {"expression": expression})

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

    def _ensure_ws(self, target_id: str = None) -> bool:
        """Ensure a persistent WebSocket connection to the target tab.

        Reuses existing connection if target hasn't changed. Auto-reconnects on failure.
        """
        ws_url = self._get_ws_url(target_id)
        if not ws_url:
            return False

        # Reuse if same target and connection alive
        if self._ws and self._ws_url == ws_url:
            try:
                self._ws.ping()
                return True
            except Exception:
                self._ws = None
                self._ws_url = None

        # Close old connection if target changed
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None
            self._ws_url = None

        # Open new persistent connection
        try:
            import websocket
            self._ws = websocket.create_connection(ws_url, timeout=10)
            self._ws_url = ws_url
            logger.info("CDP WebSocket connection established")
            return True
        except ImportError:
            return False
        except Exception as e:
            logger.error('WebSocket connect failed: %s', e)
            return False

    def _send_cdp_command(self, ws_url: str, method: str, params: dict = None) -> Any:
        """Send CDP command via persistent WebSocket (falls back to one-shot if needed)."""
        # Try persistent connection first
        if self._ws and self._ws_url == ws_url:
            try:
                self._msg_id += 1
                msg = {"id": self._msg_id, "method": method, "params": params or {}}
                self._ws.send(json.dumps(msg))
                # Read responses until we get our reply (skip events)
                deadline = time.time() + 15
                while time.time() < deadline:
                    raw = self._ws.recv()
                    response = json.loads(raw)
                    if response.get("id") == self._msg_id:
                        return response.get("result")
                    # Skip CDP events (no "id" field)
                return None
            except Exception:
                # Connection died, clean up and fall through to reconnect
                try:
                    self._ws.close()
                except Exception:
                    pass
                self._ws = None
                self._ws_url = None

        # Try to establish/re-establish persistent connection
        try:
            import websocket
            self._ws = websocket.create_connection(ws_url, timeout=10)
            self._ws_url = ws_url
            self._msg_id += 1
            msg = {"id": self._msg_id, "method": method, "params": params or {}}
            self._ws.send(json.dumps(msg))
            deadline = time.time() + 15
            while time.time() < deadline:
                raw = self._ws.recv()
                response = json.loads(raw)
                if response.get("id") == self._msg_id:
                    return response.get("result")
            return None
        except ImportError:
            return self._send_via_websocat(ws_url, method, params)
        except Exception:
            self._ws = None
            self._ws_url = None
            return None

    def _raw_cdp(self, method: str, params: dict = None) -> Any:
        """Send raw CDP command to active tab using persistent connection."""
        if not self._ensure_ws():
            return None
        return self._send_cdp_command(self._ws_url, method, params or {})

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

    def hover(self, x: int, y: int):
        """Move mouse to viewport coordinates without clicking (hover/mouseover)."""
        self._raw_cdp("Input.dispatchMouseEvent", {
            "type": "mouseMoved", "x": x, "y": y
        })

    def scroll_page(self, x: int = 0, y: int = 0, delta_x: int = 0, delta_y: int = 0):
        """Scroll the page at (x, y) by (delta_x, delta_y) pixels.

        delta_y negative = scroll up, positive = scroll down.
        delta_x negative = scroll left, positive = scroll right.
        """
        self._raw_cdp("Input.dispatchMouseEvent", {
            "type": "mouseWheel", "x": x, "y": y,
            "deltaX": delta_x, "deltaY": delta_y
        })

    def hover_selector(self, selector: str) -> Dict:
        """Hover over an element by CSS selector. Returns element bbox."""
        js = f"""(function(){{
            var el = document.querySelector({json.dumps(selector)});
            if(!el) return {{error: "not found"}};
            var r = el.getBoundingClientRect();
            el.dispatchEvent(new MouseEvent('mouseenter', {{bubbles:true}}));
            el.dispatchEvent(new MouseEvent('mouseover', {{bubbles:true}}));
            return {{x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2), width: Math.round(r.width), height: Math.round(r.height)}};
        }})()"""
        result = self.evaluate(js)
        if isinstance(result, dict) and isinstance(result.get("result"), dict):
            result = result["result"].get("value", result)
        if isinstance(result, dict) and not result.get("error"):
            # Also dispatch real mouse move for CSS :hover
            self.hover(result["x"], result["y"])
        return result

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

    def wait_for_selector(self, selector: str, timeout: float = 15, poll_interval: float = 0.3) -> Dict:
        """Wait until a CSS selector matches an element in the page.

        Returns dict with 'found', 'elapsed', and 'text' (innerText of first match).
        """
        start = time.time()
        while True:
            elapsed = time.time() - start
            try:
                result = self.evaluate(
                    f'(function(){{var el=document.querySelector({json.dumps(selector)});'
                    f'if(el)return{{found:true,text:el.innerText||"",tag:el.tagName}};'
                    f'return{{found:false}}}})()'
                )
                # Runtime.evaluate usually returns {"result": {"type": ..., "value": ...}}
                if isinstance(result, dict) and isinstance(result.get("result"), dict):
                    result = result["result"].get("value", result)
                if isinstance(result, dict) and result.get('found'):
                    result['elapsed'] = round(elapsed, 2)
                    return result
            except Exception:
                pass
            if elapsed >= timeout:
                return {"found": False, "elapsed": round(elapsed, 2), "error": f"Timeout after {timeout}s waiting for '{selector}'"}
            time.sleep(poll_interval)

    def wait_for_navigation(self, url_contains: str = None, title_contains: str = None,
                            timeout: float = 15, poll_interval: float = 0.3) -> Dict:
        """Wait until the page URL or title matches a condition.

        Returns dict with 'matched', 'url', 'title', 'elapsed'.
        """
        start = time.time()
        while True:
            elapsed = time.time() - start
            try:
                url = self.get_page_url()
                title = self.get_page_title()
                matched = False
                if url_contains and url_contains in (url or ''):
                    matched = True
                if title_contains and title_contains in (title or ''):
                    matched = True
                if not url_contains and not title_contains:
                    matched = True  # no condition = just wait for any load
                if matched:
                    return {"matched": True, "url": url, "title": title, "elapsed": round(elapsed, 2)}
            except Exception:
                pass
            if elapsed >= timeout:
                return {"matched": False, "url": url if 'url' in dir() else None,
                        "title": title if 'title' in dir() else None,
                        "elapsed": round(elapsed, 2),
                        "error": f"Timeout after {timeout}s"}
            time.sleep(poll_interval)

    def get_interactive_elements(self, max_elements: int = 100) -> List[Dict]:
        """Extract all interactive elements from the page with text, selector, and bounding box.

        Returns a list of dicts: {tag, type, text, selector, role, bbox: {x,y,width,height}, value}
        This is the web equivalent of AT-SPI's ui_tree for desktop apps.
        """
        js = """
        (function() {
            const sel = 'a, button, input, select, textarea, [role="button"], [role="link"], [role="menuitem"], [role="tab"], [role="checkbox"], [role="radio"], [onclick], [tabindex]';
            const els = document.querySelectorAll(sel);
            const results = [];
            for (let i = 0; i < Math.min(els.length, %d); i++) {
                const el = els[i];
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 && rect.height === 0) continue;
                if (rect.bottom < 0 || rect.top > window.innerHeight) continue;
                const text = (el.innerText || el.textContent || '').trim().slice(0, 100);
                const ariaLabel = el.getAttribute('aria-label') || '';
                const placeholder = el.getAttribute('placeholder') || '';
                const label = text || ariaLabel || placeholder || el.getAttribute('title') || '';
                // Build a unique selector
                let css = el.tagName.toLowerCase();
                if (el.id) css += '#' + CSS.escape(el.id);
                else if (el.name) css += '[name="' + el.name.replace(/"/g, '\\\\"') + '"]';
                else if (el.className && typeof el.className === 'string') {
                    const cls = el.className.trim().split(/\\s+/).slice(0, 2).map(c => '.' + CSS.escape(c)).join('');
                    css += cls;
                }
                results.push({
                    tag: el.tagName.toLowerCase(),
                    type: el.type || null,
                    text: label.slice(0, 80),
                    selector: css,
                    role: el.getAttribute('role') || null,
                    bbox: {x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height)},
                    value: (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') ? (el.value || '').slice(0, 50) : null
                });
            }
            return results;
        })()
        """ % max_elements
        result = self.evaluate(js)
        if isinstance(result, dict) and 'result' in result:
            val = result['result'].get('value', result.get('result'))
            if isinstance(val, list):
                return val
        if isinstance(result, list):
            return result
        return []

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


def _is_snap_launcher(launcher: List[str]) -> bool:
    """Check if a launcher command uses snap (including wrapper scripts)."""
    import shutil
    if 'snap' in launcher:
        return True
    # Check if the binary is a script that delegates to /snap/
    binary = launcher[0]
    path = shutil.which(binary)
    if not path:
        return False
    real = os.path.realpath(path)
    if '/snap/' in real:
        return True
    try:
        with open(real, 'r') as f:
            if '/snap/' in f.read(512):
                return True
    except (OSError, UnicodeDecodeError):
        pass
    return False


def _profile_dirs_for_launcher(launcher: List[str], port: int) -> List[str]:
    """Return profile dirs appropriate for this launcher type."""
    dirs: List[str] = []
    is_snap = _is_snap_launcher(launcher)

    if is_snap:
        # Snap Chromium can only write inside ~/snap/chromium/
        snap_common = os.path.join(os.path.expanduser("~"), "snap", "chromium", "common")
        if os.path.isdir(snap_common):
            dirs.append(os.path.join(snap_common, f"clawui-profile-{port}"))
        # Snap can also use /tmp
        dirs.append(os.path.join(tempfile.gettempdir(), f"clawui-cdp-snap-{port}"))
    else:
        # Non-snap: prefer stable project profile
        dirs.append(DEFAULT_USER_DATA_DIR)
        # Fallback: temp dir
        dirs.append(os.path.join(tempfile.gettempdir(), f"clawui-cdp-{port}"))

    return dirs


def sync_cookies_from_main_profile(port: int = 9222) -> bool:
    """Copy cookies from the user's main Chromium profile to the CDP headless profile.

    Enables the headless browser to share authenticated sessions (GitHub, etc.)
    from the user's regular browser without needing separate login flows.
    Both profiles must use the same --password-store (e.g., 'basic') so that
    the cookie encryption key is compatible.

    Returns True if cookies were synced successfully.
    """
    import shutil

    snap_common = os.path.join(os.path.expanduser("~"), "snap", "chromium", "common")
    src_dir = os.path.join(snap_common, "chromium", "Default")
    dst_dir = os.path.join(snap_common, f"clawui-profile-{port}", "Default")

    src = os.path.join(src_dir, "Cookies")
    dst = os.path.join(dst_dir, "Cookies")

    if not os.path.exists(src):
        # Try non-snap paths
        for candidate in [
            os.path.join(os.path.expanduser("~"), ".config", "chromium", "Default", "Cookies"),
            os.path.join(os.path.expanduser("~"), ".config", "google-chrome", "Default", "Cookies"),
        ]:
            if os.path.exists(candidate):
                src = candidate
                break
        else:
            return False

    if not os.path.isdir(os.path.dirname(dst)):
        return False

    try:
        shutil.copy2(src, dst)
        for ext in ['-wal', '-shm']:
            src_ext = src + ext
            dst_ext = dst + ext
            if os.path.exists(src_ext):
                shutil.copy2(src_ext, dst_ext)
            elif os.path.exists(dst_ext):
                os.remove(dst_ext)
        return True
    except Exception:
        return False


def launch_chromium_with_cdp(port: int = 9222, url: str = "about:blank") -> Optional[subprocess.Popen]:
    """Launch Chromium/Chrome with remote debugging enabled.

    Uses headless mode only to avoid X server dependencies.
    Smart profile selection: snap launchers get snap-accessible paths,
    native launchers get standard paths. Avoids SingletonLock permission errors.

    Returns the Popen object if successful, None otherwise.
    """

    # Candidate launchers without profile args (profile injected per-attempt)
    launcher_candidates = [
        ['chromium-browser', '--headless=new'],
        ['chromium', '--headless=new'],
        ['google-chrome', '--headless=new'],
        ['google-chrome-stable', '--headless=new'],
        ['chrome', '--headless=new'],
        ['snap', 'run', 'chromium', '--headless=new'],
        ['snap', 'run', 'chromium', '--no-sandbox', '--headless=new'],
        ['chromium-browser', '--no-sandbox', '--headless=new'],
    ]

    for launcher in launcher_candidates:
      for profile_dir in _profile_dirs_for_launcher(launcher, port):
        try:
            os.makedirs(profile_dir, exist_ok=True)
        except Exception as e:
            logger.warning('Cannot prepare profile dir %s: %s', profile_dir, e)
            continue

        # Clean stale singleton lock
        lock_path = os.path.join(profile_dir, "SingletonLock")
        if os.path.lexists(lock_path):
            try:
                os.remove(lock_path)
            except OSError:
                pass

        base_args = [
            f'--remote-debugging-port={port}',
            '--remote-allow-origins=*',
            '--no-first-run',
            '--no-default-browser-check',
            f'--user-data-dir={profile_dir}',
            url,
        ]

        cmd = launcher + base_args
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            time.sleep(3)
            if _is_port_listening(port):
                _launched_browser_processes[port] = proc
                return proc
            time.sleep(2)
            if _is_port_listening(port):
                _launched_browser_processes[port] = proc
                return proc
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                pass
            _, stderr = proc.communicate()
            if stderr:
                logger.warning("Command '%s' failed: %s", ' '.join(cmd), stderr.decode('utf-8', 'ignore')[:240])
        except FileNotFoundError:
            continue
        except Exception as e:
            logger.error("Exception launching '%s': %s", ' '.join(cmd), e)
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
    except Exception:
        return False


def discover_cdp_ports() -> List[int]:
    """Discover CDP debug ports from running Chrome/Chromium processes.

    Scans /proc for browser processes with --remote-debugging-port flags.
    Returns a list of active ports sorted by port number.
    """
    ports = set()
    browser_names = {'chrome', 'chromium', 'chromium-browser', 'google-chrome',
                     'google-chrome-stable', 'brave', 'brave-browser', 'msedge'}
    try:
        for pid_dir in os.listdir('/proc'):
            if not pid_dir.isdigit():
                continue
            try:
                cmdline_path = f'/proc/{pid_dir}/cmdline'
                with open(cmdline_path, 'rb') as f:
                    cmdline = f.read().decode('utf-8', errors='replace')
                args = cmdline.split('\x00')
                if not args:
                    continue
                # Check if this is a browser process
                exe_name = os.path.basename(args[0]).lower()
                if not any(bn in exe_name for bn in browser_names):
                    continue
                # Look for --remote-debugging-port=NNNN
                for arg in args:
                    if arg.startswith('--remote-debugging-port='):
                        try:
                            port = int(arg.split('=', 1)[1])
                            if _is_port_listening(port):
                                ports.add(port)
                        except (ValueError, IndexError):
                            pass
            except (OSError, PermissionError):
                continue
    except OSError:
        pass
    return sorted(ports)


def get_or_create_cdp_client(port: int = 9222) -> Optional[CDPClient]:
    """Get existing CDP connection or launch a browser automatically.

    If a browser is already running with CDP on the specified port, returns a client.
    Otherwise, auto-discovers CDP ports from running browsers.
    As a last resort, launches a new browser with CDP enabled.
    """
    # 1. Try the requested port first
    client = CDPClient(port=port)
    if client.is_available():
        return client

    # 2. Auto-discover CDP ports from running browser processes
    discovered = discover_cdp_ports()
    for dport in discovered:
        if dport == port:
            continue  # Already tried
        client = CDPClient(port=dport)
        if client.is_available():
            return client

    # 3. Launch a new browser as last resort
    sync_cookies_from_main_profile(port=port)
    proc = launch_chromium_with_cdp(port=port)
    if proc:
        # Wait a moment for CDP to be ready
        time.sleep(2)
        client = CDPClient(port=port)
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

