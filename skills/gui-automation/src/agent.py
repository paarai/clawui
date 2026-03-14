"""Agent loop - AI-driven GUI automation with hybrid AT-SPI + vision."""

import hashlib
import json
import re
import os
import sys
import time as _time
from functools import wraps

from .screenshot import take_screenshot, get_screen_size
from .atspi_helper import (
    list_applications, get_ui_tree_summary, find_elements,
    do_action, set_text, get_focused_element,
)
from .actions import (
    click, double_click, right_click, type_text, press_key,
    scroll, drag, focus_window, get_active_window,
)


# --- Auto Action Verification state ---
_last_screen_hash = None
_VERIFY_ACTIONS = frozenset({
    "click", "double_click", "right_click", "type_text", "press_key",
    "scroll", "drag", "do_action", "set_text", "click_element",
    "click_by_index", "click_text", "cdp_click", "cdp_type",
    "cdp_navigate", "cdp_click_at", "cdp_eval",
    "ff_click", "ff_type", "ff_navigate", "ff_eval", "launch_app",
})


def _quick_screen_hash():
    """Take a quick screenshot and return its MD5 hash, or None on failure."""
    try:
        b64 = take_screenshot(scale=True)
        return hashlib.md5(b64.encode()).hexdigest()
    except Exception:
        return None


def _with_retry(func=None, *, env_prefix="CLAWUI", category="RETRY"):
    """Decorator that adds configurable retry logic to tool functions.
    
    Reads max attempts and initial delay from env vars:
      {env_prefix}_{category}_MAX (default 3)
      {env_prefix}_{category}_DELAY (default 0.5 for general, 1.0 for CDP/Marionette/Vision)
    
    The decorated function should raise on failure. On final failure,
    returns {"type": "text", "text": "..."} with error details.
    """
    default_delay = 1.0 if category in ("CDP_RETRY", "MARIONETTE_RETRY", "VISION_RETRY") else 0.5
    
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            max_attempts = int(os.getenv(f'{env_prefix}_{category}_MAX', '3'))
            delay = float(os.getenv(f'{env_prefix}_{category}_DELAY', str(default_delay)))
            last_err = None
            for attempt in range(max_attempts):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    if attempt < max_attempts - 1:
                        print(f"[WARN] {fn.__name__}: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...", file=sys.stderr)
                        _time.sleep(delay)
                        delay *= 2
                    else:
                        return {"type": "text", "text": f"{fn.__name__} failed after {max_attempts} attempts: {last_err}"}
        return wrapper
    
    if func is not None:
        return decorator(func)
    return decorator
from .backends import get_backend
from .recorder import start_recording, stop_recording, record_action, play_recording
from .github_integration import create_github_repo

# Global recorder - use module-level functions
# CDP support (lazy import)
_cdp_client = None

def _get_cdp():
    """Get CDP client, auto-launching Chromium if needed."""
    global _cdp_client
    if _cdp_client is not None and _cdp_client.is_available():
        return _cdp_client
    try:
        from .cdp_helper import get_or_create_cdp_client
        c = get_or_create_cdp_client()
        if c and c.is_available():
            _cdp_client = c
            return _cdp_client
    except Exception as e:
        print(f"[WARN] CDP auto-launch failed: {e}", file=sys.stderr)
    return None

def _vision_find(description: str) -> tuple | None:
    """Use vision backend to locate UI element by description. Returns (x, y, confidence) or None."""
    try:
        from .vision_backend import VisionBackend
        img = take_screenshot()
        if not img:
            print("[WARN] Vision fallback: screenshot failed")
            return None
        vb = VisionBackend()
        prompt = f"Locate the UI element that matches: '{description}'. Return JSON with x, y (center coordinates), and confidence (0-1)."
        resp = vb.chat([
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}}
            ]}
        ], tools=[], system="You are a vision assistant that returns only JSON with x, y, confidence keys.")
        text = resp.get("text", "").strip()
        json_match = re.search(r'```json\\s*(\\{.*?\\})\\s*```', text, re.DOTALL) or re.search(r'\\{.*\\}', text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1) if '```' in text else json_match.group(0)
            data = json.loads(json_str)
            x = data.get("x")
            y = data.get("y")
            conf = data.get("confidence", 0.5)
            if x is not None and y is not None:
                return (int(x), int(y), float(conf))
        else:
            print(f"[WARN] Vision fallback: no JSON in response: {text[:100]}")
    except Exception as e:
        print(f"[WARN] Vision fallback error: {e}")
    return None

SYSTEM_PROMPT = """You are a GUI automation agent controlling a Linux desktop.

You have two perception modes:
1. **AT-SPI (structural)**: You receive a tree of UI elements with names, roles, positions, and available actions. This is fast and precise.
2. **Screenshot (visual)**: You see a screenshot of the screen. Use this when AT-SPI doesn't provide enough info.

Available tools:
- screenshot: Take a screenshot
- ui_tree: Get AT-SPI UI element tree for an app (or all apps)
- find_element: Search for UI elements by role and/or name
- vision_find_element: Find UI element by description using vision AI (experimental). Returns x, y, confidence.
- click: Click at coordinates (x, y) or on an element
- double_click: Double-click at coordinates
- right_click: Right-click at coordinates
- type_text: Type text
- press_key: Press key (e.g., "Return", "ctrl+c", "alt+F4")
- scroll: Scroll up/down/left/right
- drag: Drag from (x1,y1) to (x2,y2)
- focus_window: Focus a window by name
- do_action: Execute AT-SPI action on element (e.g., "click" on a button)
- set_text: Set text in an editable field via AT-SPI
- wait: Wait N seconds

Browser tools (CDP - requires Chromium with --remote-debugging-port=9222):
- cdp_navigate: Navigate browser to URL
- cdp_click: Click element by CSS selector
- cdp_click_at: Click at viewport coordinates (x,y)
- cdp_type: Type text into element by CSS selector (real keyboard events)
- cdp_eval: Evaluate JavaScript expression
- cdp_page_info: Get page title and URL
- cdp_list_tabs: List all open browser tabs
- cdp_new_tab: Open a new tab
- cdp_activate_tab: Switch to a tab by target ID
- cdp_close_tab: Close a tab by target ID
- cdp_screenshot: Take a screenshot of the browser page
- cdp_get_elements: Extract all interactive elements (buttons, links, inputs) from the page with text, selector, and bounding box — the web equivalent of ui_tree
- cdp_wait_for_selector: Wait until a CSS selector matches an element (avoids race conditions)
- cdp_wait_for_navigation: Wait until URL/title changes after navigation
- cdp_scroll: Scroll the browser page (delta_y positive=down, negative=up)
- cdp_hover: Hover over element by CSS selector (triggers :hover CSS states and mouse events)

Browser tools (Marionette - requires Firefox with --marionette):
- ff_navigate: Navigate Firefox to URL
- ff_click: Click element by CSS selector in Firefox
- ff_type: Type text into element in Firefox
- ff_eval: Execute JavaScript in Firefox
- ff_page_info: Get Firefox page title and URL
- ff_screenshot: Take screenshot of Firefox page
- ff_list_tabs: List Firefox tabs/windows
- ff_switch_tab: Switch Firefox tab by handle

Strategy:
1. First use ui_tree to understand the interface structure
2. If you can find the target element via AT-SPI, use do_action or click on its coordinates
3. If AT-SPI doesn't help, take a screenshot and use visual analysis
4. For browser tasks, use cdp_* tools (navigate, click selectors, type, eval JS)
5. After each action, verify the result (ui_tree or screenshot or cdp_page_info)
6. For file/directory/command-line tasks, prefer system tools (run_command, file_read, file_write, file_list) over GUI navigation

System/file tools (direct access, no GUI needed):
- run_command: Execute a shell command (stdout/stderr returned, 30s timeout)
- file_read: Read a file's contents (max 100KB)
- file_write: Write content to a file
- file_list: List directory contents
- open_url: Open URL in default browser

Be efficient. Prefer AT-SPI actions over coordinate clicks when available.
Prefer system tools over GUI navigation for file and command-line operations."""


def create_tools():
    return [
        {"name": "screenshot", "description": "Take a screenshot of the screen", "input_schema": {"type": "object", "properties": {}}},
        {"name": "ui_tree", "description": "Get UI element tree", "input_schema": {"type": "object", "properties": {"app_name": {"type": "string", "description": "App name filter (optional)"}}}},
        {"name": "find_element", "description": "Find UI elements by role and/or name (supports partial match)", "input_schema": {"type": "object", "properties": {"role": {"type": "string"}, "name": {"type": "string"}, "name_contains": {"type": "string"}, "role_contains": {"type": "string"}}}},
        {"name": "list_windows", "description": "List all top-level windows with title and geometry", "input_schema": {"type": "object", "properties": {}}},
        {"name": "activate_window", "description": "Activate/focus a window by title (supports partial match)", "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "title_contains": {"type": "string"}}}},
        {"name": "wait_for_window", "description": "Wait for a window with given title (or partial title) to appear, returns window info", "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "title_contains": {"type": "string"}, "timeout": {"type": "number", "default": 30}}}},
        {"name": "wait_for_element", "description": "Wait for a UI element to appear (polls AT-SPI). Returns element info when found or timeout error.", "input_schema": {"type": "object", "properties": {"role": {"type": "string", "description": "Element role (e.g. 'push button', 'text')"}, "name": {"type": "string", "description": "Exact element name"}, "name_contains": {"type": "string", "description": "Partial name match (case-insensitive)"}, "timeout": {"type": "number", "default": 15, "description": "Max seconds to wait"}}}},
        {"name": "describe_screen", "description": "Get a textual description of what's on screen using vision AI", "input_schema": {"type": "object", "properties": {"detail": {"type": "string", "enum": ["brief", "detailed"], "default": "brief"}}}},
        {"name": "click", "description": "Click at coordinates", "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]}},
        {"name": "double_click", "description": "Double-click", "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]}},
        {"name": "right_click", "description": "Right-click", "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]}},
        {"name": "type_text", "description": "Type text", "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
        {"name": "press_key", "description": "Press key combo", "input_schema": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}},
        {"name": "scroll", "description": "Scroll", "input_schema": {"type": "object", "properties": {"direction": {"type": "string", "enum": ["up", "down", "left", "right"]}, "amount": {"type": "integer"}}}},
        {"name": "drag", "description": "Drag", "input_schema": {"type": "object", "properties": {"start_x": {"type": "integer"}, "start_y": {"type": "integer"}, "end_x": {"type": "integer"}, "end_y": {"type": "integer"}}, "required": ["start_x", "start_y", "end_x", "end_y"]}},
        {"name": "focus_window", "description": "Focus window by name", "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
        {"name": "do_action", "description": "Execute AT-SPI action on element found by role+name", "input_schema": {"type": "object", "properties": {"role": {"type": "string"}, "name": {"type": "string"}, "action": {"type": "string", "default": "click"}}}},
        {"name": "set_text", "description": "Set text in editable field (by role+name)", "input_schema": {"type": "object", "properties": {"role": {"type": "string"}, "name": {"type": "string"}, "text": {"type": "string"}}, "required": ["text"]}},
        {"name": "wait", "description": "Wait seconds", "input_schema": {"type": "object", "properties": {"seconds": {"type": "number"}}, "required": ["seconds"]}},
        {"name": "vision_find_element", "description": "Find UI element by description using vision AI (experimental)", "input_schema": {"type": "object", "properties": {"description": {"type": "string"}}, "required": ["description"]}},
        # High-level element interaction (find + act in one step)
        {"name": "click_element", "description": "Find a UI element by role/name and click its center. Combines find_element + click in one step.", "input_schema": {"type": "object", "properties": {"role": {"type": "string", "description": "Element role (e.g. 'push button', 'menu item')"}, "name": {"type": "string", "description": "Exact element name"}, "name_contains": {"type": "string", "description": "Partial name match (case-insensitive)"}, "button": {"type": "string", "enum": ["left", "right", "double"], "default": "left"}}}},
        {"name": "get_element_text", "description": "Get the text/value of a UI element found by role/name. Returns name, value, and states.", "input_schema": {"type": "object", "properties": {"role": {"type": "string"}, "name": {"type": "string"}, "name_contains": {"type": "string"}}}},
        # Application launch tools
        {"name": "launch_app", "description": "Launch an application by command (e.g., 'firefox', 'gedit', or full path). Returns process info.", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string", "description": "Command to execute (with optional args)"}, "args": {"type": "array", "items": {"type": "string"}, "description": "Optional argument list"}}, "required": ["cmd"]}},
        {"name": "launch_wechat_devtools", "description": "Launch WeChat DevTools (snap or wine). Returns when window appears.", "input_schema": {"type": "object", "properties": {"use_wine": {"type": "boolean", "default": False, "description": "Use Wine backend (if Windows .exe provided)"}}}},
        # CDP tools (browser automation)
        {"name": "cdp_navigate", "description": "Navigate browser to URL (requires Chromium with --remote-debugging-port=9222)", "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
        {"name": "cdp_click", "description": "Click element by CSS selector in browser", "input_schema": {"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}},
        {"name": "cdp_type", "description": "Type text into element by CSS selector in browser", "input_schema": {"type": "object", "properties": {"selector": {"type": "string"}, "text": {"type": "string"}}, "required": ["selector", "text"]}},
        {"name": "cdp_eval", "description": "Evaluate JavaScript in browser page", "input_schema": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}},
        {"name": "cdp_page_info", "description": "Get current browser page title and URL", "input_schema": {"type": "object", "properties": {}}},
        {"name": "cdp_click_at", "description": "Click at viewport coordinates (x,y) in browser", "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]}},
        {"name": "cdp_list_tabs", "description": "List all browser tabs", "input_schema": {"type": "object", "properties": {}}},
        {"name": "cdp_new_tab", "description": "Open a new browser tab", "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}}},
        {"name": "cdp_activate_tab", "description": "Switch to a browser tab by target ID", "input_schema": {"type": "object", "properties": {"target_id": {"type": "string"}}, "required": ["target_id"]}},
        {"name": "cdp_close_tab", "description": "Close a browser tab by target ID", "input_schema": {"type": "object", "properties": {"target_id": {"type": "string"}}, "required": ["target_id"]}},
        {"name": "cdp_get_elements", "description": "Extract all interactive elements (buttons, links, inputs, selects) from the browser page with text, CSS selector, and bounding box. The web equivalent of ui_tree for desktop apps.", "input_schema": {"type": "object", "properties": {"max_elements": {"type": "integer", "default": 100, "description": "Maximum number of elements to return"}}}},
        {"name": "cdp_screenshot", "description": "Take a screenshot of the browser page", "input_schema": {"type": "object", "properties": {}}},
        {"name": "cdp_wait_for_selector", "description": "Wait until a CSS selector matches an element in the browser page. Returns match info or timeout error.", "input_schema": {"type": "object", "properties": {"selector": {"type": "string", "description": "CSS selector to wait for"}, "timeout": {"type": "number", "default": 15, "description": "Max seconds to wait"}}, "required": ["selector"]}},
        {"name": "cdp_wait_for_navigation", "description": "Wait until browser URL contains a string or title contains a string. Useful after clicking links/submitting forms.", "input_schema": {"type": "object", "properties": {"url_contains": {"type": "string", "description": "Wait until URL contains this string"}, "title_contains": {"type": "string", "description": "Wait until title contains this string"}, "timeout": {"type": "number", "default": 15, "description": "Max seconds to wait"}}}},
        {"name": "cdp_scroll", "description": "Scroll the browser page. Use delta_y positive for down, negative for up. Optionally specify (x,y) to scroll at a specific position.", "input_schema": {"type": "object", "properties": {"delta_y": {"type": "integer", "default": 300, "description": "Vertical scroll amount in pixels (positive=down, negative=up)"}, "delta_x": {"type": "integer", "default": 0, "description": "Horizontal scroll amount (positive=right, negative=left)"}, "x": {"type": "integer", "default": 400, "description": "X position to scroll at"}, "y": {"type": "integer", "default": 400, "description": "Y position to scroll at"}}}},
        {"name": "cdp_hover", "description": "Hover over an element by CSS selector in the browser (triggers :hover CSS and mouseenter/mouseover events). Returns element position.", "input_schema": {"type": "object", "properties": {"selector": {"type": "string", "description": "CSS selector of element to hover"}}, "required": ["selector"]}},
        # Marionette tools (Firefox automation)
        {"name": "ff_navigate", "description": "Navigate Firefox to URL (requires firefox --marionette)", "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
        {"name": "ff_click", "description": "Click element by CSS selector in Firefox", "input_schema": {"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}},
        {"name": "ff_type", "description": "Type text into element in Firefox", "input_schema": {"type": "object", "properties": {"selector": {"type": "string"}, "text": {"type": "string"}}, "required": ["selector", "text"]}},
        {"name": "ff_eval", "description": "Execute JavaScript in Firefox", "input_schema": {"type": "object", "properties": {"script": {"type": "string"}}, "required": ["script"]}},
        {"name": "ff_page_info", "description": "Get Firefox page title and URL", "input_schema": {"type": "object", "properties": {}}},
        {"name": "ff_screenshot", "description": "Take a screenshot of Firefox page", "input_schema": {"type": "object", "properties": {}}},
        {"name": "ff_list_tabs", "description": "List Firefox tabs/windows", "input_schema": {"type": "object", "properties": {}}},
        {"name": "ff_switch_tab", "description": "Switch Firefox tab by handle", "input_schema": {"type": "object", "properties": {"handle": {"type": "string"}}, "required": ["handle"]}},
        # Record/Replay tools
        {"name": "record_start", "description": "Start recording actions into a replayable script", "input_schema": {"type": "object", "properties": {"name": {"type": "string", "description": "Recording name"}, "description": {"type": "string"}}}},
        {"name": "record_stop", "description": "Stop recording and save to file", "input_schema": {"type": "object", "properties": {"filepath": {"type": "string", "description": "Save path (default: recordings/<name>.json)"}}}},
        {"name": "replay", "description": "Replay a recorded script", "input_schema": {"type": "object", "properties": {"filepath": {"type": "string", "description": "Path to recording JSON"}, "speed": {"type": "number", "description": "Playback speed multiplier (default 1.0)"}, "dry_run": {"type": "boolean", "description": "Preview without executing"}}, "required": ["filepath"]}},
        {"name": "list_recordings", "description": "List available recorded scripts", "input_schema": {"type": "object", "properties": {}}},
        # OCR-based text detection (fast, CPU-friendly)
        {"name": "find_text", "description": "Find text on screen using OCR (RapidOCR/Tesseract). Returns list of occurrences with center coordinates and scores. Supports partial match.", "input_schema": {"type": "object", "properties": {"text": {"type": "string", "description": "Text to find (case-insensitive partial match)"}}, "required": ["text"]}},
        {"name": "wait_for_text", "description": "Wait until specified text appears on screen using OCR polling. Returns first match coordinates and elapsed time.", "input_schema": {"type": "object", "properties": {"text": {"type": "string", "description": "Text to wait for (case-insensitive partial match)"}, "timeout": {"type": "number", "default": 30, "description": "Maximum seconds to wait"}, "poll_interval": {"type": "number", "default": 0.5, "description": "Seconds between OCR polls"}}, "required": ["text"]}},
        # OCR-based click (find text + click in one step)
        {"name": "click_text", "description": "Find text on screen via OCR and click its center. Combines find_text + click in one step. Retries up to 3 times with increasing delay if text not found.", "input_schema": {"type": "object", "properties": {"text": {"type": "string", "description": "Text to find and click (case-insensitive partial match)"}, "button": {"type": "string", "enum": ["left", "right", "double"], "default": "left"}, "index": {"type": "integer", "default": 0, "description": "Which occurrence to click if multiple matches (0=first, -1=last)"}, "timeout": {"type": "number", "default": 5, "description": "Max seconds to retry finding the text"}}, "required": ["text"]}},
        {"name": "screen_inspect", "description": "Inspect screenshot content via OCR and return detected hints/errors with recommended next actions. Use this before critical clicks if UI seems unresponsive.", "input_schema": {"type": "object", "properties": {"keywords": {"type": "array", "items": {"type": "string"}, "description": "Optional keywords to detect, e.g. ['无 AppID','错误','失败']"}}}},
        {"name": "resolve_create_blockers", "description": "Auto-handle common create-page blockers using OCR hints. Handles: missing AppID -> click 测试号, ECONNRESET -> click 重试, then try click 创建.", "input_schema": {"type": "object", "properties": {}}},
        {"name": "smart_step", "description": "Run one intelligent UI step: inspect screenshot, classify blockers, execute best action, then verify state change.", "input_schema": {"type": "object", "properties": {"goal": {"type": "string", "description": "Goal hint, e.g. 'create project' or 'dismiss error popup'"}, "dry_run": {"type": "boolean", "default": False}}}},
        # Template-based clicking (fallback when AT-SPI/vision not available)
        {"name": "click_template", "description": "Click on a UI element based on a learned template. Input: app (template name), element (key in template), optional: offset_x/y (pixel offset)", "input_schema": {"type": "object", "properties": {"app": {"type": "string"}, "element": {"type": "string"}}, "optional": ["offset_x", "offset_y"]}},
        # High-level task automation (B)
        {"name": "plan_and_execute", "description": "Given a natural language task, autonomously break it down into steps and execute using available tools. Returns final result and summary.", "input_schema": {"type": "object", "properties": {"task": {"type": "string", "description": "Natural language description of the task to accomplish"}}, "required": ["task"]}},
        {"name": "github_create_repo", "description": "Create a GitHub repository. Tries using GITHUB_TOKEN, then gh CLI, then browser automation (requires logged-in session).", "input_schema": {"type": "object", "properties": {"repo_name": {"type": "string", "description": "Repository name (e.g., 'my-repo')"}, "repo_desc": {"type": "string", "description": "Description (optional)"}}, "required": ["repo_name"]}},
        # Annotated screenshot + click by index
        {"name": "annotated_screenshot", "description": "Take a screenshot with numbered red labels on all interactive elements. Returns the annotated image + element list. Use click_by_index to click any labeled element.", "input_schema": {"type": "object", "properties": {"sources": {"type": "string", "enum": ["auto", "atspi", "cdp", "both"], "default": "auto", "description": "Element detection source"}}}},
        {"name": "click_by_index", "description": "Click an element by its number from the last annotated_screenshot. Much more reliable than coordinate guessing.", "input_schema": {"type": "object", "properties": {"index": {"type": "integer", "description": "Element number from annotated screenshot"}, "button": {"type": "string", "enum": ["left", "right", "double"], "default": "left"}}, "required": ["index"]}},
        # API-GUI hybrid tools (direct system access)
        {"name": "run_command", "description": "Execute a shell command and return stdout/stderr. Timeout 30s, output capped at 10KB.", "input_schema": {"type": "object", "properties": {"command": {"type": "string", "description": "Shell command to execute"}, "timeout": {"type": "number", "default": 30, "description": "Timeout in seconds"}, "cwd": {"type": "string", "description": "Working directory (default: home)"}}, "required": ["command"]}},
        {"name": "file_read", "description": "Read file contents (text). Max 100KB.", "input_schema": {"type": "object", "properties": {"path": {"type": "string", "description": "Absolute or relative file path"}}, "required": ["path"]}},
        {"name": "file_write", "description": "Write content to a file. Creates parent directories if needed.", "input_schema": {"type": "object", "properties": {"path": {"type": "string", "description": "File path to write"}, "content": {"type": "string", "description": "Content to write"}}, "required": ["path", "content"]}},
        {"name": "file_list", "description": "List directory contents with name, size, and type.", "input_schema": {"type": "object", "properties": {"path": {"type": "string", "description": "Directory path (default: home)"}, "pattern": {"type": "string", "description": "Glob pattern filter (e.g. '*.py')"}}}},
        {"name": "open_url", "description": "Open a URL in the default browser using xdg-open.", "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    ]


def execute_tool(name: str, input_data: dict) -> dict:
    """Execute a tool and return result."""
    global _last_screen_hash
    result = _execute_tool_inner(name, input_data)

    # Update hash when screenshot tools produce images
    if name in ("screenshot", "cdp_screenshot", "ff_screenshot", "annotated_screenshot"):
        b64 = result.get("base64")
        if b64:
            _last_screen_hash = hashlib.md5(b64.encode()).hexdigest()

    # Auto-verify state-changing actions
    if (name in _VERIFY_ACTIONS
            and os.getenv("CLAWUI_VERIFY_ACTIONS", "1") == "1"
            and _last_screen_hash is not None):
        _time.sleep(0.15)
        after_hash = _quick_screen_hash()
        if after_hash and after_hash == _last_screen_hash:
            warning = " [WARN: screen unchanged — action may have had no effect]"
            if "text" in result:
                result["text"] += warning
            else:
                result["verification"] = warning
        if after_hash:
            _last_screen_hash = after_hash

    # Record action if recording is active (skip meta-tools and screenshots)
    if name not in ("record_start", "record_stop", "replay", "list_recordings", "screenshot"):
        record_action(name, input_data, result)
    return result


def _execute_tool_inner(name: str, input_data: dict) -> dict:
    """Execute a tool and return result."""
    import time

    try:
        if name == "screenshot":
            img = take_screenshot()
            return {"type": "image", "base64": img}

        elif name == "ui_tree":
            try:
                tree = get_ui_tree_summary(app_name=input_data.get("app_name"), max_depth=5)
            except TimeoutError:
                tree = "(AT-SPI tree walk timed out — app may be unresponsive)"
            return {"type": "text", "text": tree or "(empty UI tree)"}

        elif name == "find_element":
            max_attempts = int(os.getenv('CLAWUI_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_RETRY_DELAY', '0.5'))
            role = input_data.get("role")
            el_name = input_data.get("name")
            name_contains = input_data.get("name_contains")
            role_contains = input_data.get("role_contains")
            for attempt in range(max_attempts):
                try:
                    # Get raw elements from perception
                    elements = find_elements(role=role, name=el_name)
                    # Apply fuzzy filters if provided
                    if name_contains:
                        elements = [e for e in elements if name_contains.lower() in str(e).lower()]
                    if role_contains:
                        elements = [e for e in elements if role_contains.lower() in str(e.role if hasattr(e, 'role') else e.get('role', '')).lower()]
                    if elements:
                        text = "\n".join(str(e) for e in elements[:20])
                        return {"type": "text", "text": text}
                    if attempt < max_attempts - 1:
                        print(f"[WARN] find_element: no elements (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": "(no elements found)"}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] find_element error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"Find element error after {max_attempts} attempts: {e}"}

        elif name == "click_element":
            max_attempts = int(os.getenv('CLAWUI_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_RETRY_DELAY', '0.5'))
            role = input_data.get("role")
            el_name = input_data.get("name")
            name_contains = input_data.get("name_contains")
            button = input_data.get("button", "left")
            for attempt in range(max_attempts):
                try:
                    elements = find_elements(role=role, name=el_name)
                    if name_contains:
                        elements = [e for e in elements if name_contains.lower() in (e.name if hasattr(e, 'name') else str(e)).lower()]
                    if elements:
                        el = elements[0]
                        cx, cy = el.center() if hasattr(el, 'center') else (el.x + el.width // 2, el.y + el.height // 2)
                        if button == "double":
                            double_click(cx, cy)
                        elif button == "right":
                            right_click(cx, cy)
                        else:
                            click(cx, cy)
                        return {"type": "text", "text": f"Clicked '{el.name}' ({el.role}) at ({cx}, {cy}) [{button}]"}
                    if attempt < max_attempts - 1:
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"click_element: element not found (role={role}, name={el_name}, name_contains={name_contains})"}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"click_element error: {e}"}

        elif name == "get_element_text":
            role = input_data.get("role")
            el_name = input_data.get("name")
            name_contains = input_data.get("name_contains")
            elements = find_elements(role=role, name=el_name)
            if name_contains:
                elements = [e for e in elements if name_contains.lower() in (e.name if hasattr(e, 'name') else str(e)).lower()]
            if not elements:
                return {"type": "text", "text": "(no elements found)"}
            results = []
            for el in elements[:10]:
                info = {"name": el.name, "role": el.role, "states": el.states if hasattr(el, 'states') else []}
                if hasattr(el, 'value') and el.value is not None:
                    info["value"] = el.value
                results.append(info)
            import json
            return {"type": "text", "text": json.dumps(results, ensure_ascii=False, indent=2)}

        elif name == "click":
            click(input_data["x"], input_data["y"])
            return {"type": "text", "text": f"Clicked at ({input_data['x']}, {input_data['y']})"}

        elif name == "double_click":
            double_click(input_data["x"], input_data["y"])
            return {"type": "text", "text": f"Double-clicked at ({input_data['x']}, {input_data['y']})"}

        elif name == "right_click":
            right_click(input_data["x"], input_data["y"])
            return {"type": "text", "text": f"Right-clicked at ({input_data['x']}, {input_data['y']})"}

        elif name == "type_text":
            type_text(input_data["text"])
            return {"type": "text", "text": f"Typed: {input_data['text'][:50]}..."}

        elif name == "press_key":
            press_key(input_data["key"])
            return {"type": "text", "text": f"Pressed: {input_data['key']}"}

        elif name == "scroll":
            scroll(
                direction=input_data.get("direction", "down"),
                amount=input_data.get("amount", 3),
            )
            return {"type": "text", "text": f"Scrolled {input_data.get('direction', 'down')}"}

        elif name == "drag":
            drag(input_data["start_x"], input_data["start_y"],
                 input_data["end_x"], input_data["end_y"])
            return {"type": "text", "text": "Drag completed"}

        elif name == "focus_window":
            focus_window(name=input_data["name"])
            return {"type": "text", "text": f"Focused window: {input_data['name']}"}

        elif name == "do_action":
            elements = find_elements(
                role=input_data.get("role"),
                name=input_data.get("name"),
            )
            if not elements:
                return {"type": "text", "text": "Element not found"}
            action_name = input_data.get("action", "click")
            success = do_action(elements[0], action_name)
            if not success:
                # Fallback: click on element center
                cx, cy = elements[0].center
                click(cx, cy)
                return {"type": "text", "text": f"AT-SPI action failed, clicked at center ({cx},{cy})"}
            return {"type": "text", "text": f"Action '{action_name}' on {elements[0]}"}

        elif name == "set_text":
            elements = find_elements(
                role=input_data.get("role"),
                name=input_data.get("name"),
            )
            if not elements:
                return {"type": "text", "text": "Element not found"}
            success = set_text(elements[0], input_data["text"])
            if not success:
                # Fallback: click + type
                cx, cy = elements[0].center
                click(cx, cy)
                press_key("ctrl+a")
                type_text(input_data["text"])
                return {"type": "text", "text": f"AT-SPI set_text failed, used click+type fallback"}
            return {"type": "text", "text": f"Set text on {elements[0]}"}

        elif name == "wait":
            time.sleep(input_data["seconds"])
            return {"type": "text", "text": f"Waited {input_data['seconds']}s"}

        # Enhanced window management tools (A)
        elif name == "list_windows":
            """List all top-level windows with title and geometry."""
            windows_info = []
            try:
                # Try X11 backend first if available
                from .x11_helper import list_windows as x11_list_windows, X11Window
                if x11_list_windows():
                    for w in x11_list_windows():
                        windows_info.append({
                            "title": w.title,
                            "wid": w.wid,
                            "geometry": f"{w.width}x{w.height} at ({w.x},{w.y})"
                        })
                else:
                    # Fallback to AT-SPI apps list
                    apps = list_applications()
                    for app in apps:
                        windows_info.append({"title": app, "type": "application"})
            except Exception as e:
                return {"type": "text", "text": f"list_windows error: {e}"}
            return {"type": "dict", "windows": windows_info, "count": len(windows_info)}

        elif name == "activate_window":
            title = input_data.get("title")
            title_contains = input_data.get("title_contains")
            if not title and not title_contains:
                return {"type": "text", "text": "Missing 'title' or 'title_contains'"}
            try:
                # Find window by title
                from .x11_helper import list_windows as x11_list_windows, activate_window as x11_activate
                windows = x11_list_windows()
                target = None
                if title:
                    for w in windows:
                        if title.lower() in w.title.lower():
                            target = w
                            break
                else:
                    for w in windows:
                        if title_contains.lower() in w.title.lower():
                            target = w
                            break
                if target:
                    x11_activate(target)
                    return {"type": "text", "text": f"Activated window: {target.title}"}
                else:
                    return {"type": "text", "text": f"No window matching '{title or title_contains}' found"}
            except Exception as e:
                return {"type": "text", "text": f"activate_window error: {e}"}

        elif name == "wait_for_window":
            title = input_data.get("title")
            title_contains = input_data.get("title_contains")
            timeout = input_data.get("timeout", 30)
            if not title and not title_contains:
                return {"type": "text", "text": "Missing 'title' or 'title_contains'"}
            start = time.time()
            while time.time() - start < timeout:
                try:
                    from .x11_helper import list_windows as x11_list_windows
                    windows = x11_list_windows()
                    found = None
                    if title:
                        for w in windows:
                            if title.lower() in w.title.lower():
                                found = w
                                break
                    else:
                        for w in windows:
                            if title_contains.lower() in w.title.lower():
                                found = w
                                break
                    if found:
                        return {"type": "dict", "title": found.title, "wid": found.wid, "geometry": f"{found.width}x{found.height}", "text": f"Window appeared: {found.title}"}
                except Exception:
                    pass
                time.sleep(1)
            return {"type": "text", "text": f"Timeout: window '{title or title_contains}' not found after {timeout}s"}

        elif name == "wait_for_element":
            role = input_data.get("role")
            el_name = input_data.get("name")
            name_contains = input_data.get("name_contains")
            timeout = input_data.get("timeout", 15)
            if not role and not el_name and not name_contains:
                return {"type": "text", "text": "Need at least one of: role, name, name_contains"}
            start = time.time()
            delay = 0.5
            while time.time() - start < timeout:
                try:
                    elements = find_elements(role=role, name=el_name)
                    if name_contains:
                        elements = [e for e in elements if name_contains.lower() in str(e).lower()]
                    if elements:
                        text = "\n".join(str(e) for e in elements[:10])
                        elapsed = time.time() - start
                        return {"type": "text", "text": f"Found {len(elements)} element(s) after {elapsed:.1f}s:\n{text}"}
                except Exception:
                    pass
                time.sleep(delay)
                delay = min(delay * 1.5, 2.0)
            return {"type": "text", "text": f"Timeout: no element matching role={role}, name={el_name}, name_contains={name_contains} after {timeout}s"}

        elif name == "describe_screen":
            detail = input_data.get("detail", "brief")
            try:
                # Take screenshot and use vision backend to describe
                from .vision_backend import VisionBackend
                img = take_screenshot()
                if not img:
                    return {"type": "text", "text": "Failed to take screenshot"}
                vb = VisionBackend()
                prompt = "Briefly describe what's on this screen in 2-3 sentences." if detail == "brief" else "Give a detailed description of all UI elements on this screen, including buttons, text fields, menus, and their approximate locations."
                resp = vb.chat([
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}}
                    ]}
                ], tools=[], system="You are a helpful assistant describing GUI screens.")
                text = resp.get("text", "").strip()
                return {"type": "text", "text": text}
            except Exception as e:
                return {"type": "text", "text": f"describe_screen error: {e}"}

        # B. High-level task automation (plan-and-execute)
        elif name == "plan_and_execute":
            task = input_data.get("task")
            if not task:
                return {"type": "text", "text": "Missing 'task' parameter"}
            max_steps = input_data.get("max_steps", 30)
            try:
                backend = get_backend()
            except Exception as e:
                return {"type": "text", "text": f"get_backend error: {e}"}
            
            # Prepare tools list (exclude plan_and_execute to avoid recursion)
            all_tools = create_tools()
            tools = [t for t in all_tools if t["name"] != "plan_and_execute"]
            
            messages = [{"role": "user", "content": task}]
            history = []
            step = 0
            
            while step < max_steps:
                try:
                    resp = backend.chat(messages, tools, SYSTEM_PROMPT)
                except Exception as e:
                    return {"type": "text", "text": f"LLM call failed at step {step}: {e}"}
                
                tool_calls = resp.get("tool_calls", [])
                if not tool_calls:
                    # Task complete
                    summary = resp.get("text", "")
                    return {"type": "dict", "completed": True, "summary": summary, "steps": step, "history": history}
                
                # Process each tool call
                for call in tool_calls:
                    tname = call["name"]
                    tinput = call["input"]
                    call_id = call.get("id", f"call_{step}_{len(history)}")
                    
                    # Execute the tool
                    try:
                        tresult = execute_tool(tname, tinput)
                    except Exception as e:
                        tresult = {"type": "text", "text": f"Tool execution error: {e}"}
                    
                    history.append({
                        "step": step + 1,
                        "tool": tname,
                        "input": tinput,
                        "result": tresult,
                        "call_id": call_id
                    })
                    
                    # Append assistant message with tool_use
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{"id": call_id, "type": "tool_use", "name": tname, "input": tinput}]
                    })
                    # Append user message with tool result
                    messages.append({
                        "role": "user",
                        "content": f"Tool: {tname}\nResult: {json.dumps(tresult, ensure_ascii=False)}"
                    })
                    
                step += 1
            
            return {"type": "dict", "completed": False, "summary": "Max steps reached", "steps": max_steps, "history": history}

        # Application launch tools
        elif name == "launch_app":
            cmd = input_data.get("cmd")
            args = input_data.get("args", [])
            if not cmd:
                return {"type": "text", "text": "Missing 'cmd' parameter"}
            try:
                import subprocess
                full_cmd = [cmd] + args
                proc = subprocess.Popen(full_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                time.sleep(1)  # Give it a moment to start
                return {"type": "dict", "pid": proc.pid, "cmd": full_cmd, "text": f"Launched: {full_cmd} (PID {proc.pid})"}
            except Exception as e:
                return {"type": "text", "text": f"Launch failed: {e}"}

        elif name == "launch_wechat_devtools":
            use_wine = input_data.get("use_wine", False)
            try:
                import subprocess
                if use_wine:
                    # Try Wine: look for installer or installed exe
                    wine_exe = os.path.expanduser("~/wechat-tools/wechatdevtools.exe")
                    if os.path.isfile(wine_exe):
                        # Check if already installed via Wine
                        prefix = os.environ.get("WINEPREFIX", os.path.expanduser("~/.wine"))
                        installed_exe = os.path.join(prefix, "drive_c", "Program Files (x86)", "微信开发者工具", "wechatdevtools.exe")
                        if os.path.isfile(installed_exe):
                            proc = subprocess.Popen(["wine", installed_exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                        else:
                            # Run installer first
                            return {"type": "text", "text": f"WeChat not installed in Wine. Please run: wine {wine_exe}"}
                    else:
                        return {"type": "text", "text": "No Wine installer found at ~/wechat-tools/wechatdevtools.exe"}
                else:
                    # Try snap
                    proc = subprocess.Popen(["snap", "run", "wechat-devtools"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                time.sleep(2)
                return {"type": "dict", "pid": proc.pid, "text": f"Launched WeChat DevTools (PID {proc.pid})"}
            except Exception as e:
                return {"type": "text", "text": f"Launch WeChat DevTools failed: {e}"}

        elif name == "vision_find_element":
            description = input_data.get("description", "").strip()
            if not description:
                return {"type": "text", "text": "Missing 'description' parameter"}
            try:
                from .vision_backend import VisionBackend
            except ImportError:
                return {"type": "text", "text": "VisionBackend not available"}
            img = take_screenshot()
            if not img:
                return {"type": "text", "text": "Failed to take screenshot"}
            max_attempts = int(os.getenv('CLAWUI_VISION_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_VISION_RETRY_DELAY', '1.0'))
            for attempt in range(max_attempts):
                try:
                    vb = VisionBackend()
                    prompt = f"Locate the UI element that matches: '{description}'. Return JSON with x, y (center coordinates), and confidence (0-1)."
                    resp = vb.chat([
                        {"role": "user", "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}}
                        ]}
                    ], tools=[], system="You are a vision assistant that returns only JSON with x, y, confidence keys.")
                    text = resp.get("text", "").strip()
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL) or re.search(r'\{.*\}', text, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1) if '```' in text else json_match.group(0)
                        data = json.loads(json_str)
                        x = data.get("x")
                        y = data.get("y")
                        conf = data.get("confidence", 0.5)
                        if x is not None and y is not None:
                            return {"type": "dict", "x": x, "y": y, "confidence": conf, "raw": text}
                    # No valid coordinates produced - retry if possible
                    if attempt < max_attempts - 1:
                        print(f"[WARN] vision_find_element: no coordinates (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"Vision response could not produce coordinates: {text}"}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] vision_find_element error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"Vision error after {max_attempts} attempts: {e}"}

        # CDP tools
        elif name.startswith("cdp_"):
            cdp = _get_cdp()
            if not cdp:
                if name == "cdp_navigate":
                    return {"type": "text", "text": "CDP not available. Start Chromium with --remote-debugging-port=9222"}
                return {"type": "text", "text": "CDP not available"}

            def _cdp_navigate_impl():
                cdp.navigate(input_data["url"])
                time.sleep(2)
                title = cdp.get_page_title()
                return {"type": "text", "text": f"Navigated to {input_data['url']} - Title: {title}"}

            def _cdp_click_impl():
                result = cdp.click_element(input_data["selector"])
                return {"type": "text", "text": f"Clicked '{input_data['selector']}': {result}"}

            def _cdp_type_impl():
                result = cdp.type_in_element(input_data["selector"], input_data["text"])
                return {"type": "text", "text": f"Typed into '{input_data['selector']}': {result}"}

            def _cdp_eval_impl():
                result = cdp.evaluate(input_data["expression"])
                return {"type": "text", "text": f"JS result: {json.dumps(result, ensure_ascii=False)[:500]}"}

            def _cdp_page_info_impl():
                info = {"url": cdp.get_page_url(), "title": cdp.get_page_title()}
                return {"type": "text", "text": json.dumps(info, ensure_ascii=False)}

            def _cdp_click_at_impl():
                cdp.dispatch_mouse(input_data["x"], input_data["y"])
                return {"type": "text", "text": f"Clicked at ({input_data['x']}, {input_data['y']})"}

            def _cdp_list_tabs_impl():
                tabs = cdp.client.list_targets()
                pages = [{"id": t.get("id"), "title": t.get("title", ""), "url": t.get("url", "")} for t in tabs if t.get("type") == "page"]
                return {"type": "text", "text": json.dumps(pages, ensure_ascii=False)}

            def _cdp_new_tab_impl():
                url = input_data.get("url", "about:blank")
                result = cdp.client.new_tab(url)
                return {"type": "text", "text": f"New tab: {json.dumps(result, ensure_ascii=False)[:300]}"}

            def _cdp_activate_tab_impl():
                ok = cdp.client.activate_tab(input_data["target_id"])
                return {"type": "text", "text": f"Activated: {ok}"}

            def _cdp_close_tab_impl():
                ok = cdp.client.close_tab(input_data["target_id"])
                return {"type": "text", "text": f"Closed: {ok}"}

            def _cdp_get_elements_impl():
                max_el = input_data.get("max_elements", 100)
                elements = cdp.client.get_interactive_elements(max_elements=max_el)
                if not elements:
                    return {"type": "text", "text": "(no interactive elements found on page)"}
                lines = [f"Found {len(elements)} interactive elements:"]
                for i, el in enumerate(elements):
                    bbox = el.get("bbox", {})
                    text = el.get("text", "")
                    tag = el.get("tag", "?")
                    sel = el.get("selector", "")
                    role = el.get("role") or ""
                    val = el.get("value")
                    typ = el.get("type") or ""
                    desc = f"[{i}] <{tag}{'['+typ+']' if typ else ''}> "
                    if role:
                        desc += f"role={role} "
                    desc += f'"{text}" ' if text else ""
                    if val:
                        desc += f'value="{val}" '
                    desc += f"sel=\"{sel}\" "
                    desc += f"@({bbox.get('x',0)},{bbox.get('y',0)} {bbox.get('w',0)}x{bbox.get('h',0)})"
                    lines.append(desc)
                return {"type": "text", "text": "\n".join(lines)}

            def _cdp_screenshot_impl():
                b64 = cdp.client.take_screenshot()
                if b64:
                    return {"type": "image", "base64": b64}
                raise Exception("Empty screenshot")

            def _cdp_wait_for_selector_impl():
                selector = input_data.get("selector", "")
                timeout = input_data.get("timeout", 15)
                result = cdp.client.wait_for_selector(selector, timeout=timeout)
                return {"type": "text", "text": json.dumps(result)}

            def _cdp_wait_for_navigation_impl():
                result = cdp.client.wait_for_navigation(
                    url_contains=input_data.get("url_contains"),
                    title_contains=input_data.get("title_contains"),
                    timeout=input_data.get("timeout", 15)
                )
                return {"type": "text", "text": json.dumps(result)}

            def _cdp_scroll_impl():
                x = input_data.get("x", 400)
                y = input_data.get("y", 400)
                delta_x = input_data.get("delta_x", 0)
                delta_y = input_data.get("delta_y", 300)
                cdp.client.scroll_page(x=x, y=y, delta_x=delta_x, delta_y=delta_y)
                return {"type": "text", "text": json.dumps({"scrolled": True, "delta_x": delta_x, "delta_y": delta_y})}

            def _cdp_hover_impl():
                selector = input_data.get("selector", "")
                result = cdp.client.hover_selector(selector)
                return {"type": "text", "text": json.dumps(result)}

            cdp_retry_handlers = {
                "cdp_navigate": ("CDP navigate", _cdp_navigate_impl),
                "cdp_click": ("CDP click", _cdp_click_impl),
                "cdp_type": ("CDP type", _cdp_type_impl),
                "cdp_eval": ("CDP eval", _cdp_eval_impl),
                "cdp_page_info": ("CDP page_info", _cdp_page_info_impl),
                "cdp_click_at": ("CDP click_at", _cdp_click_at_impl),
                "cdp_list_tabs": ("CDP list_tabs", _cdp_list_tabs_impl),
                "cdp_new_tab": ("CDP new_tab", _cdp_new_tab_impl),
                "cdp_activate_tab": ("CDP activate_tab", _cdp_activate_tab_impl),
                "cdp_close_tab": ("CDP close_tab", _cdp_close_tab_impl),
                "cdp_screenshot": ("CDP screenshot", _cdp_screenshot_impl),
                "cdp_scroll": ("CDP scroll", _cdp_scroll_impl),
                "cdp_hover": ("CDP hover", _cdp_hover_impl),
            }
            cdp_non_retry_handlers = {
                "cdp_get_elements": _cdp_get_elements_impl,
                "cdp_wait_for_selector": _cdp_wait_for_selector_impl,
                "cdp_wait_for_navigation": _cdp_wait_for_navigation_impl,
            }

            if name in cdp_retry_handlers:
                failure_name, handler = cdp_retry_handlers[name]
                handler.__name__ = failure_name
                return _with_retry(handler, category="CDP_RETRY")()
            if name in cdp_non_retry_handlers:
                try:
                    return cdp_non_retry_handlers[name]()
                except Exception as e:
                    if name == "cdp_get_elements":
                        return {"type": "text", "text": f"cdp_get_elements error: {e}"}
                    return {"type": "text", "text": f"Error: {e}"}

            return {"type": "text", "text": f"Unknown tool: {name}"}

        # Marionette (Firefox) tools
        elif name.startswith("ff_"):
            from .marionette_helper import get_or_create_marionette_client
            mc = get_or_create_marionette_client()
            if not mc:
                if name == "ff_navigate":
                    return {"type": "text", "text": "Marionette not available. Start Firefox with --marionette"}
                return {"type": "text", "text": "Marionette not available"}

            def _ff_navigate_impl():
                mc.navigate(input_data["url"])
                time.sleep(2)
                info = {"url": mc.get_url(), "title": mc.get_title()}
                return {"type": "text", "text": json.dumps(info, ensure_ascii=False)}

            def _ff_click_impl():
                el = mc.find_element("css selector", input_data["selector"])
                if not el:
                    return {"type": "text", "text": "Element not found"}
                ok = mc.click_element(el)
                return {"type": "text", "text": f"Click: {ok}"}

            def _ff_type_impl():
                el = mc.find_element("css selector", input_data["selector"])
                if not el:
                    return {"type": "text", "text": "Element not found"}
                mc.send_keys(el, input_data["text"])
                return {"type": "text", "text": f"Typed into {input_data['selector']}"}

            def _ff_eval_impl():
                result = mc.execute_script(input_data["script"])
                return {"type": "text", "text": json.dumps(result, ensure_ascii=False)[:500]}

            def _ff_page_info_impl():
                info = {"url": mc.get_url(), "title": mc.get_title()}
                return {"type": "text", "text": json.dumps(info, ensure_ascii=False)}

            def _ff_screenshot_impl():
                b64 = mc.take_screenshot()
                if b64:
                    return {"type": "image", "base64": b64}
                raise Exception("Empty screenshot")

            def _ff_list_tabs_impl():
                handles = mc.get_window_handles()
                return {"type": "text", "text": json.dumps(handles, ensure_ascii=False)}

            def _ff_switch_tab_impl():
                ok = mc.switch_to_window(input_data["handle"])
                return {"type": "text", "text": f"Switched: {ok}"}

            ff_handlers = {
                "ff_navigate": ("Firefox navigate", _ff_navigate_impl),
                "ff_click": ("Firefox click", _ff_click_impl),
                "ff_type": ("Firefox type", _ff_type_impl),
                "ff_eval": ("Firefox eval", _ff_eval_impl),
                "ff_page_info": ("Firefox page_info", _ff_page_info_impl),
                "ff_screenshot": ("Firefox screenshot", _ff_screenshot_impl),
                "ff_list_tabs": ("Firefox list_tabs", _ff_list_tabs_impl),
                "ff_switch_tab": ("Firefox switch_tab", _ff_switch_tab_impl),
            }

            if name in ff_handlers:
                failure_name, handler = ff_handlers[name]
                handler.__name__ = failure_name
                return _with_retry(handler, category="MARIONETTE_RETRY")()

            return {"type": "text", "text": f"Unknown tool: {name}"}

        # OCR-based tools
        elif name == "find_text":
            # Take screenshot
            img_data = take_screenshot()
            if not img_data:
                return {"type": "text", "text": "Failed to take screenshot"}
            try:
                from .ocr_tool import ocr_find_text
                matches = ocr_find_text(img_data, input_data["text"])
                return {"type": "dict", "matches": matches, "count": len(matches), "text": f"Found {len(matches)} occurrence(s) of '{input_data['text']}'"}
            except Exception as e:
                return {"type": "text", "text": f"OCR error: {e}"}

        elif name == "wait_for_text":
            text = input_data.get("text")
            if not text:
                return {"type": "text", "text": "Missing 'text' parameter"}
            timeout = input_data.get("timeout", 30)
            poll_interval = input_data.get("poll_interval", 0.5)
            start = time.time()
            while time.time() - start < timeout:
                try:
                    img_data = take_screenshot()
                    if not img_data:
                        time.sleep(poll_interval)
                        continue
                    from .ocr_tool import ocr_find_text
                    matches = ocr_find_text(img_data, text)
                    if matches:
                        elapsed = time.time() - start
                        return {"type": "dict", "matches": matches, "count": len(matches), "elapsed": round(elapsed, 2), "text": f"Text appeared after {elapsed:.1f}s: {len(matches)} occurrence(s)"}
                except Exception:
                    pass
                time.sleep(poll_interval)
            return {"type": "text", "text": f"Timeout: text '{text}' not found after {timeout}s"}

        elif name == "click_text":
            text = input_data.get("text")
            if not text:
                return {"type": "text", "text": "Missing 'text' parameter"}
            button = input_data.get("button", "left")
            index = input_data.get("index", 0)
            timeout = input_data.get("timeout", 5)
            poll_interval = 0.5
            start = time.time()
            last_err = None
            while time.time() - start < timeout:
                try:
                    img_data = take_screenshot()
                    if not img_data:
                        time.sleep(poll_interval)
                        continue
                    from .ocr_tool import ocr_find_text
                    matches = ocr_find_text(img_data, text)
                    if matches:
                        # Sort by score descending, pick by index
                        matches.sort(key=lambda m: m.get("score", 0), reverse=True)
                        if abs(index) > len(matches):
                            return {"type": "text", "text": f"Found {len(matches)} match(es) but index {index} out of range"}
                        match = matches[index]
                        cx, cy = match["center"]
                        if button == "double":
                            double_click(cx, cy)
                        elif button == "right":
                            right_click(cx, cy)
                        else:
                            click(cx, cy)
                        elapsed = round(time.time() - start, 2)
                        return {"type": "dict", "clicked": match["text"], "center": [cx, cy], "score": match.get("score"), "elapsed": elapsed, "text": f"Clicked '{match['text']}' at ({cx}, {cy}) [{button}]"}
                except Exception as e:
                    last_err = str(e)
                time.sleep(poll_interval)
            return {"type": "text", "text": f"click_text: '{text}' not found after {timeout}s" + (f" (last error: {last_err})" if last_err else "")}

        elif name == "screen_inspect":
            # OCR-first screen understanding: detect blocking hints/errors before blind clicking
            img_data = take_screenshot()
            if not img_data:
                return {"type": "text", "text": "screen_inspect: failed to take screenshot"}
            try:
                from .ocr_tool import ocr_extract_lines
                lines = ocr_extract_lines(img_data, threshold=0.2)
                texts = [str(x.get("text", "")).strip() for x in lines if str(x.get("text", "")).strip()]
                full_text = "\n".join(texts)

                default_keywords = [
                    "无 AppID", "无AppID", "测试号", "注册或使用测试号", "错误", "失败", "超时", "重新登录",
                    "access_token", "not found", "invalid", "权限", "网络"
                ]
                keywords = input_data.get("keywords") or default_keywords
                hits = []
                for kw in keywords:
                    if kw and kw in full_text:
                        hits.append(kw)

                suggestions = []
                if any(k in hits for k in ["无 AppID", "无AppID"]):
                    suggestions.append("Detected missing AppID. Click '测试号' or fill valid AppID before creating project.")
                if any(k in hits for k in ["重新登录", "access_token"]):
                    suggestions.append("Detected login/session issue. Re-login first, then retry current action.")
                if any(k in hits for k in ["网络", "超时"]):
                    suggestions.append("Detected network/timeout hint. Check network and retry with backoff.")
                if any(k in hits for k in ["错误", "失败"]):
                    suggestions.append("Detected generic error words. Read nearby OCR lines and branch workflow by error type.")

                return {
                    "type": "dict",
                    "hint_hits": hits,
                    "suggestions": suggestions,
                    "line_count": len(texts),
                    "sample_lines": texts[:30],
                    "text": f"screen_inspect: {len(hits)} hint(s) detected"
                }
            except Exception as e:
                return {"type": "text", "text": f"screen_inspect error: {e}"}

        elif name == "resolve_create_blockers":
            # Heuristic recovery flow for WeChat DevTools create/import blockers
            img_data = take_screenshot()
            if not img_data:
                return {"type": "text", "text": "resolve_create_blockers: failed to take screenshot"}
            try:
                from .ocr_tool import ocr_extract_lines, ocr_find_text
                lines = ocr_extract_lines(img_data, threshold=0.2)
                full_text = "\n".join([str(x.get("text", "")) for x in lines])
                actions = []

                # 1) Missing AppID -> try click "测试号"
                if ("无 AppID" in full_text) or ("无AppID" in full_text) or ("无 ApplID" in full_text):
                    matches = ocr_find_text(img_data, "测试号", threshold=0.2)
                    if matches:
                        matches.sort(key=lambda m: m.get("score", 0), reverse=True)
                        cx, cy = matches[0]["center"]
                        click(cx, cy)
                        actions.append(f"clicked 测试号 at ({cx},{cy})")
                        time.sleep(1.0)
                        img_data = take_screenshot() or img_data
                        full_text = "\n".join([str(x.get("text", "")) for x in ocr_extract_lines(img_data, threshold=0.2)])

                # 2) Network reset popup -> click "重试"
                if ("ECONNRESET" in full_text) or ("重试" in full_text):
                    matches = ocr_find_text(img_data, "重试", threshold=0.2)
                    if matches:
                        matches.sort(key=lambda m: m.get("score", 0), reverse=True)
                        cx, cy = matches[0]["center"]
                        click(cx, cy)
                        actions.append(f"clicked 重试 at ({cx},{cy})")
                        time.sleep(1.0)
                        img_data = take_screenshot() or img_data

                # 3) Try click "创建" if present
                matches = ocr_find_text(img_data, "创建", threshold=0.2)
                if matches:
                    # prefer right-most lower button (usually confirm)
                    matches.sort(key=lambda m: (m["center"][0], m["center"][1]))
                    cx, cy = matches[-1]["center"]
                    click(cx, cy)
                    actions.append(f"clicked 创建 at ({cx},{cy})")
                else:
                    actions.append("no 创建 button detected")

                return {"type": "dict", "actions": actions, "text": f"resolve_create_blockers done: {len(actions)} action(s)"}
            except Exception as e:
                return {"type": "text", "text": f"resolve_create_blockers error: {e}"}

        elif name == "smart_step":
            # Observe -> Decide -> Act -> Verify
            goal = input_data.get("goal", "")
            dry_run = bool(input_data.get("dry_run", False))

            img_data = take_screenshot()
            if not img_data:
                return {"type": "text", "text": "smart_step: failed to take screenshot"}

            try:
                from .ocr_tool import ocr_extract_lines, ocr_find_text

                def _full_text(data):
                    lines = ocr_extract_lines(data, threshold=0.2)
                    return "\n".join([str(x.get("text", "")) for x in lines])

                before_text = _full_text(img_data)
                plan = []

                # Decide
                if ("ECONNRESET" in before_text) or ("重试" in before_text and "下载基础库" in before_text):
                    plan.append(("click_text", "重试"))
                if ("无 AppID" in before_text) or ("无AppID" in before_text) or ("无 ApplID" in before_text):
                    plan.append(("click_text", "测试号"))
                if ("创建小程序" in before_text) or ("创建小游戏" in before_text) or ("创建" in before_text and "取消" in before_text):
                    plan.append(("click_text", "创建"))

                # Fallback generic plan
                if not plan:
                    if "关闭" in before_text:
                        plan.append(("click_text", "关闭"))
                    elif "确定" in before_text:
                        plan.append(("click_text", "确定"))

                executed = []
                if not dry_run:
                    for action, token in plan:
                        matches = ocr_find_text(img_data, token, threshold=0.2)
                        if not matches:
                            executed.append(f"skip {action}('{token}') no match")
                            continue
                        # prefer right-most/lower candidate for confirm buttons
                        matches.sort(key=lambda m: (m["center"][0], m["center"][1]))
                        cx, cy = matches[-1]["center"]
                        click(cx, cy)
                        executed.append(f"click '{token}' at ({cx},{cy})")
                        time.sleep(1.0)
                        img_data = take_screenshot() or img_data

                after_text = _full_text(img_data)

                # Verify change
                changed = before_text != after_text
                still_blocked = any(k in after_text for k in ["无 AppID", "无AppID", "ECONNRESET", "下载基础库版本"])

                return {
                    "type": "dict",
                    "goal": goal,
                    "plan": [f"{a}:{t}" for a, t in plan],
                    "executed": executed,
                    "changed": changed,
                    "still_blocked": still_blocked,
                    "text": f"smart_step: changed={changed}, blocked={still_blocked}, actions={len(executed)}"
                }
            except Exception as e:
                return {"type": "text", "text": f"smart_step error: {e}"}

        elif name == "click_template":
            app_name = input_data.get("app")
            element_name = input_data.get("element")
            if not app_name or not element_name:
                return {"type": "text", "text": "Missing 'app' or 'element'"}
            try:
                import json
                template_path = os.path.join(os.path.dirname(__file__), 'templates', f'{app_name}.json')
                if not os.path.exists(template_path):
                    return {"type": "text", "text": f"Template not found: {template_path}"}
                with open(template_path, 'r', encoding='utf-8') as f:
                    template = json.load(f)
                
                elements = template.get('elements', {})
                if element_name not in elements:
                    available = ', '.join(elements.keys())
                    return {"type": "text", "text": f"Element '{element_name}' not in template. Available: {available}"}
                
                rel_pos = elements[element_name]
                rel_x, rel_y = rel_pos['x'], rel_pos['y']
                
                # Find target window
                from .x11_helper import list_windows as x11_list_windows
                windows = x11_list_windows()
                win_title = template.get('window_title', '')
                target_win = None
                for w in windows:
                    if win_title.lower() in w.title.lower():
                        target_win = w
                        break
                if not target_win and win_title:
                    for w in windows:
                        if app_name.lower() in w.title.lower():
                            target_win = w
                            break
                if not target_win:
                    return {"type": "text", "text": f"Window for app '{app_name}' not found"}
                
                click_x = target_win.x + int(rel_x * target_win.width)
                click_y = target_win.y + int(rel_y * target_win.height)
                
                offset_x = input_data.get("offset_x", 0)
                offset_y = input_data.get("offset_y", 0)
                click_x += offset_x
                click_y += offset_y
                
                from .actions import click
                click(click_x, click_y)
                return {"type": "dict", "x": click_x, "y": click_y, "target_window": target_win.title, "text": f"Clicked {element_name} at ({click_x},{click_y})"}
            except Exception as e:
                return {"type": "text", "text": f"click_template error: {e}"}

        # Record/Replay tools
        elif name == "record_start":
            rec_dir = os.path.join(os.path.dirname(__file__), "..", "recordings")
            os.makedirs(rec_dir, exist_ok=True)
            rec_name = (input_data.get("name") or "").strip()
            if rec_name:
                safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "_", rec_name)
                filepath = os.path.join(rec_dir, f"{safe_name}.json")
            else:
                filepath = None
            rec = start_recording(filepath=filepath)
            return {"type": "text", "text": f"Recording started: {rec.filepath}"}

        elif name == "record_stop":
            saved = stop_recording()
            if not saved:
                return {"type": "text", "text": "No active recording session"}
            return {"type": "text", "text": f"Recording saved: {saved}"}

        elif name == "replay":
            filepath = input_data.get("filepath")
            if not filepath:
                return {"type": "text", "text": "Missing 'filepath'"}
            speed = float(input_data.get("speed", 1.0) or 1.0)
            dry_run = bool(input_data.get("dry_run", False))
            delay = 0.5 / speed if speed > 0 else 0.0
            results = play_recording(filepath, execute_tool, delay=delay, dry_run=dry_run)
            return {"type": "text", "text": f"Replayed {len(results)} actions (dry_run={dry_run}, speed={speed})"}

        elif name == "list_recordings":
            rec_dir = os.path.join(os.path.dirname(__file__), "..", "recordings")
            if not os.path.isdir(rec_dir):
                return {"type": "text", "text": "No recordings found"}
            files = sorted([f for f in os.listdir(rec_dir) if f.endswith(".json")])
            if not files:
                return {"type": "text", "text": "No recordings found"}
            return {"type": "text", "text": "\n".join([f"- {f}" for f in files])}

        elif name == "github_create_repo":
            repo_name = input_data.get("repo_name")
            repo_desc = input_data.get("repo_desc", "")
            if not repo_name:
                return {"type": "text", "text": "Missing 'repo_name' parameter"}
            try:
                result = create_github_repo(repo_name, repo_desc)
                if result.get("success"):
                    return {"type": "text", "text": f"✅ GitHub repository created: {result.get('repo_url')} (via {result.get('method')})"}
                else:
                    return {"type": "text", "text": f"❌ Failed to create GitHub repository: {result.get('error')} (method: {result.get('method')})"}
            except Exception as e:
                return {"type": "text", "text": f"Error during GitHub repo creation: {e}"}

        elif name == "annotated_screenshot":
            from .annotated_screenshot import annotated_screenshot as _ann_ss
            sources = input_data.get("sources", "auto")
            img_b64, elements = _ann_ss(sources=sources)
            element_list = "\n".join(
                f"  [{e.index}] {e.role} '{e.name}' at ({e.center_x},{e.center_y})"
                for e in elements
            )
            summary = f"Found {len(elements)} interactive elements:\n{element_list}"
            return {"type": "image_and_text", "base64": img_b64, "text": summary}

        elif name == "click_by_index":
            from .annotated_screenshot import get_last_elements
            idx = input_data.get("index")
            button = input_data.get("button", "left")
            elements = get_last_elements()
            if not elements:
                return {"type": "text", "text": "No annotated screenshot taken yet. Use annotated_screenshot first."}
            target = None
            for el in elements:
                if el.index == idx:
                    target = el
                    break
            if not target:
                return {"type": "text", "text": f"Element #{idx} not found. Valid: 1-{len(elements)}"}
            x, y = target.center_x, target.center_y
            if button == "double":
                double_click(x, y)
            elif button == "right":
                right_click(x, y)
            else:
                click(x, y)
            return {"type": "text", "text": f"Clicked [{idx}] '{target.name}' ({target.role}) at ({x},{y})"}

        # --- API-GUI hybrid tools ---
        elif name == "run_command":
            import subprocess as _sp
            if os.getenv("CLAWUI_ALLOW_SHELL", "1") == "0":
                return {"type": "text", "text": "Shell commands disabled (CLAWUI_ALLOW_SHELL=0)"}
            command = input_data.get("command", "")
            timeout = min(float(input_data.get("timeout", 30)), 120)
            cwd = input_data.get("cwd") or os.path.expanduser("~")
            try:
                r = _sp.run(
                    command, shell=True, capture_output=True, text=True,
                    timeout=timeout, cwd=cwd,
                )
                out = r.stdout[:10240] or "(empty)"
                err = r.stderr[:2048]
                text = f"exit={r.returncode}\n--- stdout ---\n{out}"
                if err:
                    text += f"\n--- stderr ---\n{err}"
                return {"type": "text", "text": text}
            except _sp.TimeoutExpired:
                return {"type": "text", "text": f"Command timed out after {timeout}s"}

        elif name == "file_read":
            path = os.path.expanduser(input_data.get("path", ""))
            if not os.path.isfile(path):
                return {"type": "text", "text": f"File not found: {path}"}
            size = os.path.getsize(path)
            if size > 102400:
                return {"type": "text", "text": f"File too large: {size} bytes (max 100KB)"}
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return {"type": "text", "text": content}

        elif name == "file_write":
            path = os.path.expanduser(input_data.get("path", ""))
            content = input_data.get("content", "")
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"type": "text", "text": f"Written {len(content)} bytes to {path}"}

        elif name == "file_list":
            import glob as _glob
            dir_path = os.path.expanduser(input_data.get("path", "~"))
            pattern = input_data.get("pattern", "*")
            if not os.path.isdir(dir_path):
                return {"type": "text", "text": f"Directory not found: {dir_path}"}
            entries = sorted(_glob.glob(os.path.join(dir_path, pattern)))
            lines = []
            for e in entries[:200]:
                try:
                    st = os.stat(e)
                    kind = "dir" if os.path.isdir(e) else "file"
                    lines.append(f"{kind}  {st.st_size:>10}  {os.path.basename(e)}")
                except OSError:
                    lines.append(f"???  {'?':>10}  {os.path.basename(e)}")
            return {"type": "text", "text": "\n".join(lines) or "(empty directory)"}

        elif name == "open_url":
            import subprocess as _sp
            url = input_data.get("url", "")
            _sp.Popen(["xdg-open", url], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
            return {"type": "text", "text": f"Opened {url} in default browser"}

        else:
            return {"type": "text", "text": f"Unknown tool: {name}"}

    except Exception as e:
        return {"type": "text", "text": f"Error: {e}"}


def run_agent(task: str, max_steps: int = 30, model: str = "claude-sonnet-4-20250514",
              log_file: str = None):
    """
    Run the GUI automation agent for a given task.
    
    Args:
        task: Natural language description of what to do
        max_steps: Maximum number of tool-use steps
        model: AI model to use
        log_file: Optional path to write structured JSON run log
    """
    import datetime
    backend = get_backend(model)
    tools = create_tools()

    # Structured run log for debugging and replay analysis
    run_log = {
        "task": task,
        "model": model,
        "max_steps": max_steps,
        "started_at": datetime.datetime.now().isoformat(),
        "steps": [],
        "result": None,
        "status": "running",
    }

    # Initial context: provide UI tree + active window
    active = get_active_window()
    apps = list_applications()
    initial_context = f"Active window: {active['name']}\nRunning apps: {', '.join(apps)}\n\nTask: {task}"

    messages = [{"role": "user", "content": initial_context}]
    consecutive_errors = 0
    last_response = None

    def _save_log():
        """Write run log to file if configured."""
        if not log_file:
            return
        run_log["finished_at"] = datetime.datetime.now().isoformat()
        try:
            os.makedirs(os.path.dirname(log_file) if os.path.dirname(log_file) else ".", exist_ok=True)
            with open(log_file, "w") as f:
                json.dump(run_log, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WARN] Failed to write run log: {e}", file=sys.stderr)

    for step in range(max_steps):
        print(f"\n--- Step {step + 1}/{max_steps} ---")

        try:
            response = backend.chat(
                messages=messages,
                tools=tools,
                system=SYSTEM_PROMPT,
            )
            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            print(f"Backend error: {e}")
            run_log["steps"].append({"step": step + 1, "error": str(e), "type": "backend_error"})
            if consecutive_errors >= 3:
                run_log["status"] = "error"
                run_log["result"] = f"3 consecutive backend errors. Last: {e}"
                _save_log()
                return f"Agent stopped: 3 consecutive backend errors. Last: {e}"
            messages.append({"role": "user", "content": f"[System] Backend error occurred: {e}. Please retry."})
            continue

        last_response = response

        # Process response
        assistant_content = []
        tool_uses = []

        for block in response["raw_content"]:
            if block.type == "text":
                print(f"Agent: {block.text}")
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                print(f"Tool: {block.name}({json.dumps(block.input, ensure_ascii=False)[:100]})")
                assistant_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
                tool_uses.append(block)

        messages.append({"role": "assistant", "content": assistant_content})

        if not tool_uses:
            print("Agent finished (no more tool calls).")
            # Log final text from assistant
            for block in response["raw_content"]:
                if block.type == "text":
                    run_log["result"] = block.text
            run_log["status"] = "completed"
            _save_log()
            break

        # Execute tools
        step_log = {"step": step + 1, "tools": [], "type": "tool_step"}
        tool_results = []
        for tool_use in tool_uses:
            t0 = _time.time()
            tool_result = execute_tool(tool_use.name, tool_use.input)
            elapsed = round(_time.time() - t0, 3)

            # Log tool execution (skip base64 image data to keep log small)
            tool_log_entry = {
                "name": tool_use.name,
                "input": tool_use.input,
                "result_type": tool_result.get("type", "text"),
                "elapsed_s": elapsed,
            }
            if tool_result.get("text"):
                tool_log_entry["result_text"] = tool_result["text"][:500]
            step_log["tools"].append(tool_log_entry)

            result_type = tool_result.get("type", "text")

            if result_type == "image":
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": [{
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": tool_result["base64"],
                        }
                    }],
                })
            elif result_type == "image_and_text":
                # Annotated screenshots: send both image and text description
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": tool_result["base64"],
                            }
                        },
                        {
                            "type": "text",
                            "text": tool_result.get("text", ""),
                        }
                    ],
                })
            elif result_type == "dict":
                # Structured data results (e.g., list_windows)
                result_copy = {k: v for k, v in tool_result.items() if k != "type"}
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result_copy, ensure_ascii=False, indent=2),
                })
            else:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": tool_result.get("text", str(tool_result)),
                })

        messages.append({"role": "user", "content": tool_results})
        run_log["steps"].append(step_log)

    if run_log["status"] == "running":
        run_log["status"] = "max_steps_reached"
    if last_response and last_response.get("text"):
        run_log["result"] = last_response["text"]
    _save_log()

    if last_response and last_response.get("text"):
        return last_response["text"]
    return "Task completed."


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m src.agent 'Open Firefox and go to google.com'")
        sys.exit(1)
    final = run_agent(" ".join(sys.argv[1:]))
    print(f"\nResult: {final}")
