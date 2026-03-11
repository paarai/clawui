"""Unified perception layer - auto-route between AT-SPI and X11 backends."""

import sys
import subprocess
from typing import List, Tuple, Optional

# Import backends
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


def _is_xwayland_app(app_name: str) -> bool:
    """Check if app typically runs under XWayland."""
    xwayland_apps = {'firefox', 'chromium', 'chrome', 'brave', 'discord', 'spotify', 'slack', 'teams', 'vscode'}
    return any(x in app_name.lower() for x in xwayland_apps)


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
    """List all applications (merge AT-SPI and X11)."""
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
        if _is_xwayland_app(app_name) and X11_AVAILABLE:
            return x11_tree(app_name=app_name)[0]
        elif ATSPI_AVAILABLE:
            return atspi_tree(app_name=app_name, max_depth=max_depth)
        else:
            return "No backend available"

    # No app filter: try both
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
