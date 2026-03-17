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
import functools
import json
import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("clawui")


# ---------------------------------------------------------------------------
# Retry decorator for flaky UI operations
# ---------------------------------------------------------------------------

def retry(
    max_attempts: int = 3,
    delay: float = 0.5,
    backoff: float = 1.5,
    exceptions: tuple = (RuntimeError, TimeoutError, OSError, ConnectionError),
):
    """Retry decorator with exponential backoff for flaky UI operations.

    Args:
        max_attempts: Maximum number of attempts (default 3).
        delay: Initial delay between retries in seconds.
        backoff: Multiplier applied to delay after each retry.
        exceptions: Tuple of exception types to catch and retry.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempts = kwargs.pop("_retry_attempts", max_attempts)
            if attempts <= 1:
                return func(*args, **kwargs)
            last_exc = None
            current_delay = delay
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < attempts:
                        logger.debug(
                            "clawui: %s attempt %d/%d failed (%s), retrying in %.1fs",
                            func.__name__, attempt, attempts, e, current_delay,
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


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


@retry(max_attempts=2, delay=0.5)
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

@retry(max_attempts=3, delay=0.3)
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


@retry(max_attempts=3, delay=0.3)
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


@retry(max_attempts=3, delay=0.3)
def right_click(
    text: Optional[str] = None,
    coords: Optional[tuple[int, int]] = None,
):
    """Right-click a UI element by text label or screen coordinates."""
    from .actions import right_click as _rclick

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

def _clear_value_js() -> str:
    """Return JS snippet to clear an input's value (Python 3.10 compatible)."""
    return 'best.value = "";'


class _BrowserAPI:
    """Browser automation via Chrome DevTools Protocol."""

    def __init__(self):
        self._helper = None

    def _get_helper(self):
        if self._helper is None:
            from .cdp_helper import CDPClient as CDPHelper
            self._helper = CDPHelper()
            self._helper.connect()
        return self._helper

    def connect(self, port: int = 9222):
        """Connect to a browser's CDP debug port."""
        from .cdp_helper import CDPClient as CDPHelper
        self._helper = CDPHelper(port=port)
        self._helper.connect()

    @retry(max_attempts=2, delay=1.0, exceptions=(RuntimeError, OSError, ConnectionError, ConnectionRefusedError))
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

    @retry(max_attempts=3, delay=0.5)
    def click_text(self, text: str, exact: bool = False):
        """Click on an element containing the given text.

        Searches all visible elements in the DOM, prioritizing interactive
        elements (buttons, links, inputs) over static ones (spans, divs).

        Args:
            text: Text to search for.
            exact: If True, match the full trimmed textContent exactly.
                   If False (default), match as substring.
        """
        h = self._get_helper()
        js = f'''
        (function() {{
            const searchText = {json.dumps(text)};
            const exact = {json.dumps(exact)};
            // Priority tiers: interactive first, then any visible element
            const interactive = 'a, button, input, select, textarea, [role="button"], [role="link"], [role="menuitem"], [role="tab"], [onclick], [tabindex]';
            const allVisible = '*';

            function matches(el) {{
                const t = el.textContent ? el.textContent.trim() : '';
                if (!t) return false;
                if (exact) return t === searchText;
                return t.toLowerCase().includes(searchText.toLowerCase());
            }}

            function isVisible(el) {{
                if (!el.offsetParent && el.tagName !== 'BODY' && el.tagName !== 'HTML') return false;
                const style = window.getComputedStyle(el);
                return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
            }}

            function findSmallest(selector) {{
                const els = document.querySelectorAll(selector);
                let best = null;
                let bestLen = Infinity;
                for (const el of els) {{
                    if (!matches(el) || !isVisible(el)) continue;
                    const len = (el.textContent || '').length;
                    if (len < bestLen) {{ best = el; bestLen = len; }}
                }}
                return best;
            }}

            // Try interactive elements first (smallest matching text = most specific)
            let el = findSmallest(interactive);
            if (!el) el = findSmallest(allVisible);
            if (el) {{ el.click(); return "clicked"; }}
            return "not found";
        }})()
        '''
        result = h.evaluate(js)
        if result and result.get("result", {}).get("value") == "not found":
            raise RuntimeError(f"No clickable element with text '{text}'")

    @retry(max_attempts=2, delay=0.5)
    def click_selector(self, selector: str):
        """Click an element matching a CSS selector.

        Args:
            selector: CSS selector for the target element.

        Raises:
            RuntimeError: If no element matches the selector.
        """
        h = self._get_helper()
        result = h.evaluate(f'''
        (function() {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) return "not found";
            el.click();
            return "clicked";
        }})()
        ''')
        if result and result.get("result", {}).get("value") == "not found":
            raise RuntimeError(f"No element matching selector '{selector}'")

    def type_into(self, selector: str, text: str, clear: bool = True):
        """Type text into an input element matching a CSS selector.

        Uses proper DOM events (focus, input, change) for compatibility
        with React, Vue, Angular and other frontend frameworks.

        Args:
            selector: CSS selector for the target input element.
            text: Text to type.
            clear: Clear existing value before typing (default True).
        """
        h = self._get_helper()
        result = h.evaluate(f'''
        (function() {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) return "not found";
            el.focus();
            el.dispatchEvent(new Event('focus', {{bubbles:true}}));
            {'el.value = "";' if clear else ''}
            const nativeSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            )?.set || Object.getOwnPropertyDescriptor(
                window.HTMLTextAreaElement.prototype, 'value'
            )?.set;
            if (nativeSetter) {{
                nativeSetter.call(el, {json.dumps(text)});
            }} else {{
                el.value = {json.dumps(text)};
            }}
            el.dispatchEvent(new Event('input', {{bubbles:true}}));
            el.dispatchEvent(new Event('change', {{bubbles:true}}));
            return "ok";
        }})()
        ''')
        val = result.get("result", {}).get("value", "") if result else ""
        if val == "not found":
            raise RuntimeError(f"No element matching selector '{selector}'")

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

    def fill(self, label_or_placeholder: str, text: str, clear: bool = True):
        """Fill an input field by its label text, placeholder, or aria-label.

        This is the user-friendly way to interact with forms — no CSS selectors needed.

        Args:
            label_or_placeholder: The visible label, placeholder text, or aria-label
                of the input field (case-insensitive substring match).
            text: Text to fill in.
            clear: Clear existing value first (default True).

        Raises:
            RuntimeError: If no matching input field is found.

        Examples:
            browser.fill("Email", "user@example.com")
            browser.fill("Password", "secret123")
            browser.fill("Search", "ClawUI")
        """
        h = self._get_helper()
        result = h.evaluate(f'''
        (function() {{
            const search = {json.dumps(label_or_placeholder)}.toLowerCase();
            const inputs = document.querySelectorAll('input, textarea, select, [contenteditable="true"]');

            function matchScore(el) {{
                // Check placeholder
                const ph = (el.getAttribute('placeholder') || '').toLowerCase();
                if (ph && ph.includes(search)) return 3;
                // Check aria-label
                const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                if (aria && aria.includes(search)) return 3;
                // Check name/id
                const name = (el.getAttribute('name') || '').toLowerCase();
                const id = el.id ? el.id.toLowerCase() : '';
                if (name.includes(search) || id.includes(search)) return 2;
                // Check associated <label>
                if (el.id) {{
                    const lbl = document.querySelector('label[for="' + el.id + '"]');
                    if (lbl && lbl.textContent.toLowerCase().includes(search)) return 4;
                }}
                // Check parent/sibling label
                const parent = el.closest('label');
                if (parent && parent.textContent.toLowerCase().includes(search)) return 4;
                // Check preceding sibling or nearby text
                const prev = el.previousElementSibling;
                if (prev && prev.textContent.toLowerCase().includes(search)) return 1;
                return 0;
            }}

            let best = null;
            let bestScore = 0;
            for (const el of inputs) {{
                const s = matchScore(el);
                if (s > bestScore) {{ best = el; bestScore = s; }}
            }}

            if (!best) return JSON.stringify({{error: "not found"}});

            best.focus();
            best.dispatchEvent(new Event('focus', {{bubbles:true}}));
            {_clear_value_js() if clear else ''}
            const nativeSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            )?.set || Object.getOwnPropertyDescriptor(
                window.HTMLTextAreaElement.prototype, 'value'
            )?.set;
            if (nativeSetter) {{
                nativeSetter.call(best, {json.dumps(text)});
            }} else {{
                best.value = {json.dumps(text)};
            }}
            best.dispatchEvent(new Event('input', {{bubbles:true}}));
            best.dispatchEvent(new Event('change', {{bubbles:true}}));
            return JSON.stringify({{ok: true, tag: best.tagName, type: best.type || ""}});
        }})()
        ''')
        val = result.get("result", {}).get("value", "")
        if isinstance(val, str) and "not found" in val:
            raise RuntimeError(
                f"No input field matching '{label_or_placeholder}'. "
                "Try browser.type_into(selector, text) with a CSS selector instead."
            )

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

    def go_back(self):
        """Navigate back in browser history."""
        h = self._get_helper()
        h.evaluate('window.history.back()')

    def go_forward(self):
        """Navigate forward in browser history."""
        h = self._get_helper()
        h.evaluate('window.history.forward()')

    def reload(self):
        """Reload the current page."""
        h = self._get_helper()
        h.evaluate('window.location.reload()')

    def select_option(self, selector_or_label: str, value: str, by: str = "text"):
        """Select an option from a <select> dropdown.

        Args:
            selector_or_label: CSS selector or label text for the <select> element.
                If it starts with a CSS selector character (#, ., [), treated as selector.
                Otherwise, searches by label/placeholder like fill().
            value: The option to select.
            by: Match option by "text" (visible text), "value" (value attr), or "index".

        Raises:
            RuntimeError: If select element or option not found.
        """
        h = self._get_helper()
        result = h.evaluate(f'''
        (function() {{
            const selectorOrLabel = {json.dumps(selector_or_label)};
            const val = {json.dumps(value)};
            const by = {json.dumps(by)};

            let sel = null;
            // Try as CSS selector first if it looks like one
            if (/^[#.\\[]/.test(selectorOrLabel)) {{
                sel = document.querySelector(selectorOrLabel);
            }}
            if (!sel) {{
                // Search by label like fill() does
                const search = selectorOrLabel.toLowerCase();
                const selects = document.querySelectorAll('select');
                for (const s of selects) {{
                    const ph = (s.getAttribute('aria-label') || '').toLowerCase();
                    if (ph.includes(search)) {{ sel = s; break; }}
                    if (s.id) {{
                        const lbl = document.querySelector('label[for="' + s.id + '"]');
                        if (lbl && lbl.textContent.toLowerCase().includes(search)) {{ sel = s; break; }}
                    }}
                    const parent = s.closest('label');
                    if (parent && parent.textContent.toLowerCase().includes(search)) {{ sel = s; break; }}
                    const name = (s.getAttribute('name') || '').toLowerCase();
                    if (name.includes(search)) {{ sel = s; break; }}
                }}
            }}
            if (!sel || sel.tagName !== 'SELECT') return JSON.stringify({{error: "select not found"}});

            const opts = sel.options;
            for (let i = 0; i < opts.length; i++) {{
                const opt = opts[i];
                let match = false;
                if (by === "text") match = opt.textContent.trim().toLowerCase().includes(val.toLowerCase());
                else if (by === "value") match = opt.value === val;
                else if (by === "index") match = i === parseInt(val);
                if (match) {{
                    sel.value = opt.value;
                    sel.dispatchEvent(new Event('change', {{bubbles: true}}));
                    return JSON.stringify({{ok: true, selected: opt.textContent.trim()}});
                }}
            }}
            return JSON.stringify({{error: "option not found"}});
        }})()
        ''')
        val = result.get("result", {}).get("value", "")
        if isinstance(val, str) and "not found" in val:
            raise RuntimeError(f"select_option failed: {val}")

    def check(self, selector_or_label: str, checked: bool = True):
        """Check or uncheck a checkbox/radio input.

        Args:
            selector_or_label: CSS selector or label text for the checkbox.
            checked: True to check, False to uncheck.

        Raises:
            RuntimeError: If checkbox not found.
        """
        h = self._get_helper()
        result = h.evaluate(f'''
        (function() {{
            const selectorOrLabel = {json.dumps(selector_or_label)};
            const want = {json.dumps(checked)};
            let el = null;
            if (/^[#.\\[]/.test(selectorOrLabel)) {{
                el = document.querySelector(selectorOrLabel);
            }}
            if (!el) {{
                const search = selectorOrLabel.toLowerCase();
                const inputs = document.querySelectorAll('input[type="checkbox"], input[type="radio"]');
                for (const inp of inputs) {{
                    if (inp.id) {{
                        const lbl = document.querySelector('label[for="' + inp.id + '"]');
                        if (lbl && lbl.textContent.toLowerCase().includes(search)) {{ el = inp; break; }}
                    }}
                    const parent = inp.closest('label');
                    if (parent && parent.textContent.toLowerCase().includes(search)) {{ el = inp; break; }}
                    const aria = (inp.getAttribute('aria-label') || '').toLowerCase();
                    if (aria.includes(search)) {{ el = inp; break; }}
                }}
            }}
            if (!el) return "not found";
            if (el.checked !== want) {{ el.click(); }}
            return "ok";
        }})()
        ''')
        if result and result.get("result", {}).get("value") == "not found":
            raise RuntimeError(f"No checkbox matching '{selector_or_label}'")

    def new_tab(self, url: str = "about:blank"):
        """Open a new browser tab and navigate to the URL.

        Args:
            url: URL to open in the new tab (default: blank page).
        """
        h = self._get_helper()
        h.send("Target.createTarget", {"url": url})

    def close_tab(self, index: Optional[int] = None):
        """Close a browser tab.

        Args:
            index: Tab index to close. If None, closes the current tab.
        """
        h = self._get_helper()
        if index is not None:
            tab_list = h.list_tabs()
            if 0 <= index < len(tab_list):
                h.send("Target.closeTarget", {"targetId": tab_list[index]["id"]})
        else:
            h.evaluate('window.close()')

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
