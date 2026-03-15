"""ClawUI Public Python API — clean, importable interface for GUI automation.

Usage:
    from clawui.api import screenshot, click, type_text, find_elements
    from clawui.api import browser, apps, tree

Examples:
    # Take a screenshot
    img_bytes = screenshot()
    screenshot(save_to="screen.png")

    # Find and click elements
    buttons = find_elements(role="push button", name="OK")
    click(text="OK")
    click(coords=(100, 200))

    # Type text
    type_text("Hello, world!")
    press_key("ctrl+s")

    # Annotated screenshot (Set-of-Mark)
    png, elements = annotate(save_to="annotated.png")
    print(elements)  # [{index: 1, role: "push button", name: "OK", ...}, ...]
    click_index(3)   # Click element #3

    # Browser automation
    browser.navigate("https://example.com")
    browser.click_text("Login")
    html = browser.get_html()

    # List apps and UI tree
    app_list = apps()
    ui_tree = tree(app="Firefox")
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Desktop: Screenshot
# ---------------------------------------------------------------------------

def screenshot(
    save_to: Optional[str] = None,
    region: Optional[tuple[int, int, int, int]] = None,
    scale: bool = True,
) -> bytes:
    """Take a screenshot, return PNG bytes. Optionally save to file.

    Args:
        save_to: File path to save the PNG (optional).
        region: (x, y, width, height) crop region (optional).
        scale: Downscale large images for efficiency.

    Returns:
        Raw PNG bytes.
    """
    from .screenshot import take_screenshot

    b64 = take_screenshot(
        region=region,
        scale=scale,
    )
    raw = base64.b64decode(b64)
    if save_to:
        Path(save_to).write_bytes(raw)
    return raw


# ---------------------------------------------------------------------------
# Desktop: Apps & UI Tree
# ---------------------------------------------------------------------------

def apps() -> list[str]:
    """List all running applications visible to AT-SPI."""
    from .atspi_helper import list_applications
    return list_applications()


def tree(app: Optional[str] = None, max_depth: int = 5) -> str:
    """Get a text summary of the UI element tree.

    Args:
        app: Filter by application name (optional).
        max_depth: Maximum tree depth (default 5).

    Returns:
        Human/AI-readable indented tree string.
    """
    from .atspi_helper import get_ui_tree_summary
    return get_ui_tree_summary(app_name=app, max_depth=max_depth)


def find_elements(
    role: Optional[str] = None,
    name: Optional[str] = None,
    max_depth: int = 10,
    visible_only: bool = True,
) -> list:
    """Find UI elements matching criteria via AT-SPI.

    Args:
        role: Filter by role (e.g. 'push button', 'text', 'menu item').
        name: Filter by name (substring, case-insensitive).
        max_depth: Maximum search depth.
        visible_only: Only return visible/showing elements.

    Returns:
        List of UIElement objects with .name, .role, .center, etc.
    """
    from .atspi_helper import find_elements as _find
    return _find(role=role, name=name, max_depth=max_depth, visible_only=visible_only)


def focused_element():
    """Get the currently focused UI element, or None."""
    from .atspi_helper import get_focused_element
    return get_focused_element()


# ---------------------------------------------------------------------------
# Desktop: Input Actions
# ---------------------------------------------------------------------------

def click(
    text: Optional[str] = None,
    coords: Optional[tuple[int, int]] = None,
    button: int = 1,
):
    """Click a UI element by text label or screen coordinates.

    Args:
        text: Find element by name and click its center.
        coords: (x, y) screen coordinates to click.
        button: Mouse button (1=left, 2=middle, 3=right).

    Raises:
        ValueError: If neither text nor coords provided.
        RuntimeError: If element not found.
    """
    from .actions import click as _click

    if coords:
        _click(x=coords[0], y=coords[1], button={1: "left", 2: "middle", 3: "right"}.get(button, "left"))
    elif text:
        elems = find_elements(name=text)
        if not elems:
            raise RuntimeError(f"No element found with text '{text}'")
        cx, cy = elems[0].center
        _click(x=cx, y=cy, button={1: "left", 2: "middle", 3: "right"}.get(button, "left"))
    else:
        raise ValueError("Provide either text= or coords=")


def double_click(coords: Optional[tuple[int, int]] = None, text: Optional[str] = None):
    """Double-click at coordinates or on element matching text."""
    from .actions import double_click as _dblclick

    if coords:
        _dblclick(x=coords[0], y=coords[1])
    elif text:
        elems = find_elements(name=text)
        if not elems:
            raise RuntimeError(f"No element found with text '{text}'")
        cx, cy = elems[0].center
        _dblclick(x=cx, y=cy)
    else:
        raise ValueError("Provide either text= or coords=")


def type_text(text: str):
    """Type text using keyboard simulation."""
    from .actions import type_text as _type
    _type(text)


def press_key(key: str):
    """Press a key or key combination (e.g. 'ctrl+s', 'Return', 'alt+F4')."""
    from .actions import press_key as _press
    _press(key)


def right_click(
    text: Optional[str] = None,
    coords: Optional[tuple[int, int]] = None,
):
    """Right-click a UI element by text label or screen coordinates."""
    from .actions import right_click as _rclick, click as _click

    if coords:
        _rclick(x=coords[0], y=coords[1])
    elif text:
        elems = find_elements(name=text)
        if not elems:
            raise RuntimeError(f"No element found with text '{text}'")
        cx, cy = elems[0].center
        _rclick(x=cx, y=cy)
    else:
        _rclick()


def drag(start: tuple[int, int], end: tuple[int, int]):
    """Drag from start (x, y) to end (x, y) coordinates.

    Args:
        start: (x, y) starting position.
        end: (x, y) ending position.
    """
    from .actions import drag as _drag
    _drag(start[0], start[1], end[0], end[1])


def scroll(direction: str = "down", clicks: int = 3, coords: Optional[tuple[int, int]] = None):
    """Scroll the screen.

    Args:
        direction: 'up' or 'down'.
        clicks: Number of scroll clicks.
        coords: Optional (x, y) position to scroll at.
    """
    from .actions import scroll as _scroll
    _scroll(direction, clicks, x=coords[0] if coords else None, y=coords[1] if coords else None)


def move_mouse(x: int, y: int):
    """Move the mouse cursor to screen coordinates."""
    from .actions import mouse_move
    mouse_move(x, y)


def hotkey(*keys: str):
    """Press a hotkey combination (e.g. hotkey('ctrl', 's')).

    Args:
        *keys: Key names to press together.
    """
    from .actions import hotkey as _hotkey
    _hotkey(*keys)


# ---------------------------------------------------------------------------
# Desktop: Window Management
# ---------------------------------------------------------------------------

def focus_window(name: Optional[str] = None, window_id: Optional[int] = None):
    """Focus a window by name or X11 window ID."""
    from .actions import focus_window as _focus
    _focus(name=name, window_id=window_id)


def active_window() -> dict:
    """Get info about the currently active window. Returns {id, name}."""
    from .actions import get_active_window
    return get_active_window()


def minimize():
    """Minimize the active window."""
    from .actions import minimize_window
    minimize_window()


def maximize():
    """Maximize the active window."""
    from .actions import maximize_window
    maximize_window()


def close():
    """Close the active window (Alt+F4)."""
    from .actions import close_window
    close_window()


# ---------------------------------------------------------------------------
# Desktop: Windows (X11 / XWayland)
# ---------------------------------------------------------------------------

def windows() -> list[dict]:
    """List all X11/XWayland windows with geometry."""
    from .x11_helper import list_windows
    return list_windows()


# ---------------------------------------------------------------------------
# Browser: CDP automation
# ---------------------------------------------------------------------------

class _BrowserAPI:
    """Browser automation via Chrome DevTools Protocol."""

    def __init__(self):
        self._helper = None

    def _get_helper(self):
        if self._helper is None:
            from .cdp_helper import CDPHelper
            self._helper = CDPHelper()
            self._helper.connect()
        return self._helper

    def connect(self, port: int = 9222):
        """Connect to a browser's CDP debug port."""
        from .cdp_helper import CDPHelper
        self._helper = CDPHelper(port=port)
        self._helper.connect()

    def navigate(self, url: str, wait: bool = True):
        """Navigate to a URL.

        Args:
            url: Target URL.
            wait: Wait for page load (default True).
        """
        h = self._get_helper()
        h.navigate(url)
        if wait:
            import time
            time.sleep(1)

    def click_text(self, text: str):
        """Click on an element containing the given text."""
        h = self._get_helper()
        js = f'''
        (function() {{
            const els = document.querySelectorAll('a, button, input, [role="button"], [onclick]');
            for (const el of els) {{
                if (el.textContent && el.textContent.trim().includes({json.dumps(text)})) {{
                    el.click();
                    return "clicked";
                }}
            }}
            return "not found";
        }})()
        '''
        result = h.evaluate(js)
        if result and result.get("result", {}).get("value") == "not found":
            raise RuntimeError(f"No clickable element with text '{text}'")

    def click_selector(self, selector: str):
        """Click an element matching a CSS selector."""
        h = self._get_helper()
        h.evaluate(f'document.querySelector({json.dumps(selector)}).click()')

    def type_into(self, selector: str, text: str):
        """Type text into an input element matching a CSS selector."""
        h = self._get_helper()
        h.evaluate(f'''
        (function() {{
            const el = document.querySelector({json.dumps(selector)});
            if (el) {{ el.focus(); el.value = {json.dumps(text)}; 
                       el.dispatchEvent(new Event('input', {{bubbles:true}})); }}
        }})()
        ''')

    def get_html(self, selector: str = "body") -> str:
        """Get innerHTML of an element."""
        h = self._get_helper()
        result = h.evaluate(
            f'document.querySelector({json.dumps(selector)}).innerHTML'
        )
        return result.get("result", {}).get("value", "")

    def get_text(self, selector: str = "body") -> str:
        """Get innerText of an element."""
        h = self._get_helper()
        result = h.evaluate(
            f'document.querySelector({json.dumps(selector)}).innerText'
        )
        return result.get("result", {}).get("value", "")

    def get_url(self) -> str:
        """Get current page URL."""
        h = self._get_helper()
        result = h.evaluate('window.location.href')
        return result.get("result", {}).get("value", "")

    def get_title(self) -> str:
        """Get current page title."""
        h = self._get_helper()
        result = h.evaluate('document.title')
        return result.get("result", {}).get("value", "")

    def evaluate(self, js: str):
        """Execute arbitrary JavaScript and return the result."""
        h = self._get_helper()
        return h.evaluate(js)

    def screenshot(self, save_to: Optional[str] = None) -> bytes:
        """Take a browser screenshot, return PNG bytes."""
        h = self._get_helper()
        b64 = h.screenshot()
        raw = base64.b64decode(b64)
        if save_to:
            Path(save_to).write_bytes(raw)
        return raw

    def tabs(self) -> list[dict]:
        """List open browser tabs."""
        h = self._get_helper()
        return h.list_tabs()

    def switch_tab(self, index: int):
        """Switch to a tab by index."""
        h = self._get_helper()
        tab_list = h.list_tabs()
        if 0 <= index < len(tab_list):
            h.activate_tab(tab_list[index]["id"])

    def wait_for(self, selector: str, timeout: float = 10.0) -> bool:
        """Wait for a CSS selector to appear in the DOM.

        Returns True if found, False if timed out.
        """
        import time
        h = self._get_helper()
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = h.evaluate(
                f'!!document.querySelector({json.dumps(selector)})'
            )
            if result.get("result", {}).get("value") is True:
                return True
            time.sleep(0.5)
        return False

    def close(self):
        """Close the CDP connection."""
        if self._helper:
            self._helper.close()
            self._helper = None


# Singleton browser API instance
browser = _BrowserAPI()


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

def ocr(save_to: Optional[str] = None) -> list[dict]:
    """Run OCR on current screen, return list of {text, x, y, w, h, confidence}.

    Args:
        save_to: Optional path to save the screenshot used for OCR.
    """
    from .ocr_tool import ocr_extract_lines
    return ocr_extract_lines()


# ---------------------------------------------------------------------------
# Convenience: wait helpers
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Annotated Screenshots (Set-of-Mark)
# ---------------------------------------------------------------------------

def annotate(sources: str = "auto", save_to: Optional[str] = None) -> tuple[bytes, list[dict]]:
    """Take an annotated screenshot with numbered labels on interactive elements.

    This implements the "Set-of-Mark" pattern: each interactive element gets a
    red numbered label. Use click_index() to click any labeled element.

    Args:
        sources: Element detection source — "atspi", "cdp", "both", or "auto".
        save_to: Optional file path to save the annotated PNG.

    Returns:
        (png_bytes, elements) where elements is a list of dicts with keys:
        index, role, name, center, x, y, width, height, source, selector.
    """
    from .annotated_screenshot import annotated_screenshot

    b64, labeled = annotated_screenshot(sources=sources)
    raw = base64.b64decode(b64)
    if save_to:
        Path(save_to).write_bytes(raw)
    return raw, [el.to_dict() for el in labeled]


def click_index(index: int, button: int = 1):
    """Click an element by its index from the last annotated screenshot.

    Args:
        index: The numbered label from annotate() (1-based).
        button: Mouse button (1=left, 2=middle, 3=right).

    Raises:
        IndexError: If index is out of range.
        RuntimeError: If no annotated screenshot has been taken.
    """
    from .annotated_screenshot import get_last_elements
    from .actions import click as _click

    elements = get_last_elements()
    if not elements:
        raise RuntimeError("No annotated screenshot taken yet. Call annotate() first.")
    matches = [e for e in elements if e.index == index]
    if not matches:
        raise IndexError(f"No element with index {index}. Valid: 1–{len(elements)}")
    el = matches[0]
    _click(
        x=el.center_x, y=el.center_y,
        button={1: "left", 2: "middle", 3: "right"}.get(button, "left"),
    )


def wait_for_element(
    name: Optional[str] = None,
    role: Optional[str] = None,
    timeout: float = 10.0,
    interval: float = 0.5,
):
    """Wait for a UI element to appear. Returns the element or raises TimeoutError."""
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        elems = find_elements(role=role, name=name)
        if elems:
            return elems[0]
        time.sleep(interval)
    raise TimeoutError(f"Element (name={name}, role={role}) not found within {timeout}s")


def wait_for_text(
    text: str,
    timeout: float = 10.0,
    interval: float = 1.0,
    fuzzy: bool = False,
    max_edit_distance: int = 2,
) -> bool:
    """Wait for text to appear on screen via OCR. Returns True if found.

    Args:
        text: Text to search for (case-insensitive substring match).
        timeout: Max seconds to wait.
        interval: Seconds between OCR polls.
        fuzzy: Enable fuzzy matching to tolerate OCR errors.
        max_edit_distance: Max Levenshtein distance for fuzzy matching.
    """
    import time
    from .ocr_tool import _fuzzy_match

    deadline = time.time() + timeout
    while time.time() < deadline:
        lines = ocr()
        for line in lines:
            line_text = line.get("text", "")
            if fuzzy:
                if _fuzzy_match(text, line_text, max_edit_distance):
                    return True
            else:
                if text.lower() in line_text.lower():
                    return True
        time.sleep(interval)
    return False
