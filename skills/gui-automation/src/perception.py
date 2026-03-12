"""Unified perception layer - auto-route between AT-SPI, X11, and CDP backends."""

import json
import sys
import subprocess
from typing import List, Tuple, Optional

# Import backends
# Support both relative and absolute imports
try:
    from .atspi_helper import (
        list_applications as atspi_list_apps,
        get_ui_tree_summary as atspi_tree,
        find_elements as atspi_find,
        do_action as atspi_do_action,
        set_text as atspi_set_text,
    )
    ATSPI_AVAILABLE = True
except Exception:
    try:
        from src.atspi_helper import (
            list_applications as atspi_list_apps,
            get_ui_tree_summary as atspi_tree,
            find_elements as atspi_find,
            do_action as atspi_do_action,
            set_text as atspi_set_text,
        )
        ATSPI_AVAILABLE = True
    except Exception as e:
        ATSPI_AVAILABLE = False
        print(f"[WARN] AT-SPI not available: {e}", file=sys.stderr)

try:
    from .x11_helper import (
        list_windows as x11_list_windows,
        X11Window,
        get_ui_tree_summary as x11_tree,
        activate_window as x11_activate,
        click_window as x11_click,
        click_at as x11_click_at,
        type_text as x11_type,
        key_press as x11_key,
        find_windows_by_class as x11_find_by_class,
        find_windows_by_title as x11_find_by_title,
        do_action as x11_do_action,
        set_text as x11_set_text,
        list_applications as x11_list_apps,
    )
    X11_AVAILABLE = True
except Exception:
    try:
        from src.x11_helper import (
            list_windows as x11_list_windows,
            X11Window,
            get_ui_tree_summary as x11_tree,
            activate_window as x11_activate,
            click_window as x11_click,
            click_at as x11_click_at,
            type_text as x11_type,
            key_press as x11_key,
            find_windows_by_class as x11_find_by_class,
            find_windows_by_title as x11_find_by_title,
            do_action as x11_do_action,
            set_text as x11_set_text,
            list_applications as x11_list_apps,
        )
        X11_AVAILABLE = True
    except Exception as e:
        X11_AVAILABLE = False
        print(f"[WARN] X11 backend not available: {e}", file=sys.stderr)

try:
    from .cdp_helper import CDPClient
    _cdp_client = CDPClient()
    CDP_AVAILABLE = _cdp_client.is_available()
except Exception:
    try:
        from src.cdp_helper import CDPClient
        _cdp_client = CDPClient()
        CDP_AVAILABLE = _cdp_client.is_available()
    except Exception as e:
        CDP_AVAILABLE = False
        _cdp_client = None
        print(f"[WARN] CDP not available: {e}", file=sys.stderr)

# Marionette backend (Firefox)
try:
    from .marionette_helper import MarionetteClient
    _marionette_client = MarionetteClient()
    MARIONETTE_AVAILABLE = _marionette_client._connect()
    if MARIONETTE_AVAILABLE:
        _marionette_client.close()
except Exception:
    try:
        from src.marionette_helper import MarionetteClient
        _marionette_client = MarionetteClient()
        MARIONETTE_AVAILABLE = _marionette_client._connect()
        if MARIONETTE_AVAILABLE:
            _marionette_client.close()
    except Exception as e:
        MARIONETTE_AVAILABLE = False
        _marionette_client = None
        print(f"[WARN] Marionette not available: {e}", file=sys.stderr)


def _get_cdp_client() -> Optional['CDPClient']:
    """Get CDP client, re-checking availability if needed."""
    global CDP_AVAILABLE, _cdp_client
    if _cdp_client and _cdp_client.is_available():
        CDP_AVAILABLE = True
        return _cdp_client
    # Try reconnecting
    try:
        try:
            from .cdp_helper import CDPClient
        except ImportError:
            from src.cdp_helper import CDPClient
        _cdp_client = CDPClient()
        CDP_AVAILABLE = _cdp_client.is_available()
        return _cdp_client if CDP_AVAILABLE else None
    except:
        CDP_AVAILABLE = False
        return None


def _get_marionette_client() -> Optional['MarionetteClient']:
    """Get Marionette client for Firefox, re-checking availability."""
    global MARIONETTE_AVAILABLE, _marionette_client
    if _marionette_client:
        try:
            # Quick check: can we connect? (_connect will set _sock if successful)
            # Note: _connect() does a socket connect and reads hello; it's safe to test.
            # We don't want to keep the connection open all the time; we'll use on-demand.
            if _marionette_client._connect():
                # Connection succeeded, port is open. Close the test socket.
                _marionette_client.close()
                MARIONETTE_AVAILABLE = True
                # Return a fresh client wrapper that will reconnect on use.
                # Actually, we can return the same client; it will reconnect on next use.
                return _marionette_client
        except Exception:
            pass
    # Try (re)connecting: create a new client and check availability
    try:
        try:
            from .marionette_helper import MarionetteClient
        except ImportError:
            from src.marionette_helper import MarionetteClient
        _marionette_client = MarionetteClient()
        if _marionette_client._connect():
            _marionette_client.close()  # close test socket; client will reconnect on use
            MARIONETTE_AVAILABLE = True
            return _marionette_client
    except Exception:
        pass
    MARIONETTE_AVAILABLE = False
    return None


def _is_firefox(app_name: str) -> bool:
    """Check if app is Firefox (best served by Marionette)."""
    return 'firefox' in app_name.lower()


def _is_browser_app(app_name: str) -> bool:
    """Check if app is a Chromium-based browser (best served by CDP)."""
    browsers = {'chromium', 'chrome', 'brave', 'edge'}
    return any(b in app_name.lower() for b in browsers)


def _is_xwayland_app(app_name: str) -> bool:
    """Check if app typically runs under XWayland."""
    xwayland_apps = {'firefox', 'chromium', 'chrome', 'brave', 'discord', 'spotify', 'slack', 'teams', 'vscode'}
    return any(x in app_name.lower() for x in xwayland_apps)


def _get_marionette_summary(mario: 'MarionetteClient') -> str:
    """Get Firefox browser state summary via Marionette."""
    try:
        # Ensure we have a working connection (MarionetteClient has reconnect logic)
        # The client passed is from _get_marionette_client which handles availability
        lines = ["Firefox (Marionette):"]

        # Get current page info directly from client
        title = mario.get_title() or "unknown"
        url = mario.get_url() or "unknown"
        lines.append(f"  Title: {title}")
        lines.append(f"  URL: {url}")

        # Try to get page interactive elements via JavaScript
        try:
            result = mario.execute_script('''
                var els = document.querySelectorAll('input,select,textarea,button,[role=button]');
                var items = [];
                for (var i = 0; i < Math.min(els.length, 30); i++) {
                    var el = els[i];
                    items.push({
                        tag: el.tagName.toLowerCase(),
                        type: el.type || '',
                        name: el.name || el.id || '',
                        text: (el.textContent || el.value || '').substring(0,50).trim()
                    });
                }
                return JSON.stringify(items);
            ''')
            if result:
                # result might be a string (JSON) or already parsed dict
                elements = json.loads(result) if isinstance(result, str) else result
                if elements:
                    lines.append(f"  Interactive elements ({len(elements)}):")
                    for el in elements:
                        name = el.get("name") or el.get("text", "")[:30]
                        lines.append(f"    <{el['tag']}> type={el.get('type','')} name=\"{name}\"")
        except Exception:
            pass

        return "\n".join(lines)
    except Exception:
        return "Firefox (Marionette): connected but unable to get page info"


def _get_cdp_summary(cdp: 'CDPClient', detailed: bool = False) -> str:
    """Get a summary of browser state via CDP.
    
    Args:
        cdp: CDPClient instance
        detailed: If True, include page DOM summary for active tab
    """
    tabs = cdp.list_targets()
    pages = [t for t in tabs if t.get("type") == "page"]
    if not pages:
        return ""
    
    lines = [f"Browser: {len(pages)} tab(s)"]
    for i, tab in enumerate(pages):
        marker = " *" if i == 0 else ""  # First tab is usually active
        title = tab.get("title", "(untitled)")[:60]
        url = tab.get("url", "")
        tid = tab.get("id", "")
        lines.append(f"  [{i+1}]{marker} {title}")
        lines.append(f"      url: {url}")
        lines.append(f"      id: {tid}")
    
    if detailed and pages:
        # Get active tab's page structure (forms, links, buttons)
        try:
            result = cdp.evaluate('''(function() {
                var info = {title: document.title, url: location.href};
                var forms = Array.from(document.querySelectorAll('input,select,textarea,button,[role=button]')).slice(0,30).map(function(el) {
                    return {
                        tag: el.tagName.toLowerCase(),
                        type: el.type || '',
                        name: el.name || el.id || '',
                        role: el.getAttribute('role') || '',
                        text: (el.textContent || el.value || '').substring(0,50).trim(),
                        visible: el.offsetParent !== null
                    };
                });
                info.interactive_elements = forms;
                return JSON.stringify(info);
            })()''')
            if result and isinstance(result, dict):
                val = result.get("result", {}).get("value", "")
                if val:
                    page_info = json.loads(val)
                    lines.append(f"\n  Active page: {page_info.get('title', '')}")
                    elements = page_info.get('interactive_elements', [])
                    if elements:
                        lines.append(f"  Interactive elements ({len(elements)}):")
                        for el in elements:
                            vis = "✓" if el.get("visible") else "hidden"
                            name = el.get("name") or el.get("text", "")[:30]
                            lines.append(f"    <{el['tag']}> type={el.get('type','')} name=\"{name}\" [{vis}]")
        except:
            pass
    
    return "\n".join(lines)


def _has_x11_windows() -> bool:
    """Check if there are any X11 windows."""
    if not X11_AVAILABLE:
        return False
    try:
        windows = x11_list_windows()
        return len(windows) > 0
    except:
        return False


def list_applications() -> List[str]:
    """List all applications (merge AT-SPI, X11, and CDP browser tabs)."""
    apps = []
    if ATSPI_AVAILABLE:
        try:
            apps.extend(atspi_list_apps())
        except:
            pass
    if X11_AVAILABLE:
        try:
            apps.extend(x11_list_apps())
        except:
            pass
    # Add CDP browser info
    cdp = _get_cdp_client()
    if cdp:
        tabs = cdp.list_targets()
        pages = [t for t in tabs if t.get("type") == "page"]
        if pages:
            apps.append(f"Chromium ({len(pages)} tabs)")
    # Add Marionette Firefox info
    mario = _get_marionette_client()
    if mario:
        apps.append("Firefox (Marionette)")
    # Deduplicate
    return sorted(set(apps))


def get_ui_tree_summary(app_name: Optional[str] = None, max_depth: int = 5) -> str:
    """
    Get UI tree summary. Auto-select backend based on app_name:
    - If app is known XWayland (Firefox, Chromium...), use X11
    - If no app specified and both backends available, merge results
    """
    # Specific app request
    if app_name:
        # Chromium-based: prefer CDP
        if _is_browser_app(app_name):
            cdp = _get_cdp_client()
            if cdp:
                return _get_cdp_summary(cdp, detailed=True)
        # Firefox: prefer Marionette
        if _is_firefox(app_name):
            mario = _get_marionette_client()
            if mario:
                return _get_marionette_summary(mario)
        if _is_xwayland_app(app_name) and X11_AVAILABLE:
            return x11_tree(app_name=app_name)[0]
        elif ATSPI_AVAILABLE:
            return atspi_tree(app_name=app_name, max_depth=max_depth)
        else:
            return "No backend available"

    # No app filter: try all backends
    parts = []
    if ATSPI_AVAILABLE:
        try:
            atspi_out = atspi_tree(app_name=None, max_depth=max_depth)
            if atspi_out.strip():
                parts.append("=== AT-SPI (Wayland native) ===\n" + atspi_out)
        except:
            pass
    if X11_AVAILABLE:
        try:
            x11_out = x11_tree(app_name=None, max_depth=max_depth)[0]
            if x11_out.strip():
                parts.append("=== X11 (XWayland) ===\n" + x11_out)
        except:
            pass
    # CDP: include browser tab list
    cdp = _get_cdp_client()
    if cdp:
        try:
            cdp_summary = _get_cdp_summary(cdp)
            if cdp_summary:
                parts.append("=== CDP (Chromium) ===\n" + cdp_summary)
        except:
            pass
    # Marionette: include Firefox info
    mario = _get_marionette_client()
    if mario:
        try:
            mario_summary = _get_marionette_summary(mario)
            if mario_summary:
                parts.append("=== Marionette (Firefox) ===\n" + mario_summary)
        except:
            pass

    return "\n\n".join(parts) if parts else "No UI tree available"


def find_elements(role=None, name=None, app_name=None) -> List:
    """Find elements by role/name. Select backend based on app_name."""
    if app_name and _is_xwayland_app(app_name) and X11_AVAILABLE:
        # X11: match windows by class or title
        if role:
            results = x11_find_by_class(role)
        else:
            results = x11_list_windows()
        if name:
            results = [w for w in results if name.lower() in w.title.lower()]
        return results
    else:
        if ATSPI_AVAILABLE:
            return atspi_find(role=role, name=name)
    return []


def do_action(element, action_name: str, value=None):
    """Perform action on element (auto-dispatch)."""
    # X11 window objects have attribute 'wid'
    if hasattr(element, 'wid'):
        if X11_AVAILABLE:
            return x11_do_action(element, action_name, value)
        raise RuntimeError("X11 backend not available")
    else:
        # AT-SPI element (dict with x,y)
        if ATSPI_AVAILABLE:
            return atspi_do_action(element, action_name, value)
        raise RuntimeError("AT-SPI backend not available")


def set_text(element, text: str):
    """Set text on element."""
    if hasattr(element, 'wid'):
        if X11_AVAILABLE:
            return x11_set_text(element, text)
        raise RuntimeError("X11 backend not available")
    else:
        if ATSPI_AVAILABLE:
            return atspi_set_text(element, text)
        raise RuntimeError("AT-SPI backend not available")


def activate_window(element):
    """Activate/focus a window."""
    if hasattr(element, 'wid'):
        if X11_AVAILABLE:
            x11_activate(element.wid)
            return True
    else:
        # AT-SPI element may have _node with get_window?
        # Defer to do_action
        return do_action(element, "activate")
    return False


def click_at(x: int, y: int, button: int = 1):
    """Click at coordinates (X11 only for now)."""
    if X11_AVAILABLE:
        return x11_click_at(x, y, button)
    else:
        raise RuntimeError("X11 backend required for absolute click")


def type_text(text: str):
    """Type text (global)."""
    if X11_AVAILABLE:
        return x11_type(text)
    else:
        raise RuntimeError("X11 backend required for typing")
