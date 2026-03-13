"""Agent loop - AI-driven GUI automation with hybrid AT-SPI + vision."""

import json
import re
import os
import sys

from .screenshot import take_screenshot, get_screen_size
from .atspi_helper import (
    list_applications, get_ui_tree_summary, find_elements,
    do_action, set_text, get_focused_element,
)
from .actions import (
    click, double_click, right_click, type_text, press_key,
    scroll, drag, focus_window, get_active_window,
)
from .backends import get_backend
from .recorder import Recorder, Player, start_recording, stop_recording, record_action, play_recording
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

Be efficient. Prefer AT-SPI actions over coordinate clicks when available.
"""


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
        {"name": "cdp_screenshot", "description": "Take a screenshot of the browser page", "input_schema": {"type": "object", "properties": {}}},
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
        # Template-based clicking (fallback when AT-SPI/vision not available)
        {"name": "click_template", "description": "Click on a UI element based on a learned template. Input: app (template name), element (key in template), optional: offset_x/y (pixel offset)", "input_schema": {"type": "object", "properties": {"app": {"type": "string"}, "element": {"type": "string"}}, "optional": ["offset_x", "offset_y"]}},
        # High-level task automation (B)
        {"name": "plan_and_execute", "description": "Given a natural language task, autonomously break it down into steps and execute using available tools. Returns final result and summary.", "input_schema": {"type": "object", "properties": {"task": {"type": "string", "description": "Natural language description of the task to accomplish"}}, "required": ["task"]}},
        {"name": "github_create_repo", "description": "Create a GitHub repository. Tries using GITHUB_TOKEN, then gh CLI, then browser automation (requires logged-in session).", "input_schema": {"type": "object", "properties": {"repo_name": {"type": "string", "description": "Repository name (e.g., 'my-repo')"}, "repo_desc": {"type": "string", "description": "Description (optional)"}}, "required": ["repo_name"]}},
    ]


def execute_tool(name: str, input_data: dict) -> dict:
    """Execute a tool and return result."""
    result = _execute_tool_inner(name, input_data)
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
            tree = get_ui_tree_summary(app_name=input_data.get("app_name"), max_depth=5)
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
        elif name == "cdp_navigate":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available. Start Chromium with --remote-debugging-port=9222"}
            max_attempts = int(os.getenv('CLAWUI_CDP_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_CDP_RETRY_DELAY', '1.0'))
            for attempt in range(max_attempts):
                try:
                    cdp.navigate(input_data["url"])
                    time.sleep(2)
                    title = cdp.get_page_title()
                    return {"type": "text", "text": f"Navigated to {input_data['url']} - Title: {title}"}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] cdp_navigate error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"CDP navigate failed after {max_attempts} attempts: {e}"}

        elif name == "cdp_click":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available"}
            max_attempts = int(os.getenv('CLAWUI_CDP_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_CDP_RETRY_DELAY', '1.0'))
            for attempt in range(max_attempts):
                try:
                    result = cdp.click_element(input_data["selector"])
                    return {"type": "text", "text": f"Clicked '{input_data['selector']}': {result}"}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] cdp_click error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"CDP click failed after {max_attempts} attempts: {e}"}

        elif name == "cdp_type":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available"}
            max_attempts = int(os.getenv('CLAWUI_CDP_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_CDP_RETRY_DELAY', '1.0'))
            for attempt in range(max_attempts):
                try:
                    result = cdp.type_in_element(input_data["selector"], input_data["text"])
                    return {"type": "text", "text": f"Typed into '{input_data['selector']}': {result}"}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] cdp_type error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"CDP type failed after {max_attempts} attempts: {e}"}

        elif name == "cdp_eval":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available"}
            max_attempts = int(os.getenv('CLAWUI_CDP_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_CDP_RETRY_DELAY', '1.0'))
            for attempt in range(max_attempts):
                try:
                    result = cdp.evaluate(input_data["expression"])
                    return {"type": "text", "text": f"JS result: {json.dumps(result, ensure_ascii=False)[:500]}"}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] cdp_eval error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"CDP eval failed after {max_attempts} attempts: {e}"}

        elif name == "cdp_page_info":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available"}
            max_attempts = int(os.getenv('CLAWUI_CDP_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_CDP_RETRY_DELAY', '1.0'))
            for attempt in range(max_attempts):
                try:
                    info = {"url": cdp.get_page_url(), "title": cdp.get_page_title()}
                    return {"type": "text", "text": json.dumps(info, ensure_ascii=False)}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] cdp_page_info error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"CDP page_info failed after {max_attempts} attempts: {e}"}

        elif name == "cdp_click_at":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available"}
            max_attempts = int(os.getenv('CLAWUI_CDP_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_CDP_RETRY_DELAY', '1.0'))
            for attempt in range(max_attempts):
                try:
                    cdp.dispatch_mouse(input_data["x"], input_data["y"])
                    return {"type": "text", "text": f"Clicked at ({input_data['x']}, {input_data['y']})"}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] cdp_click_at error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"CDP click_at failed after {max_attempts} attempts: {e}"}

        elif name == "cdp_list_tabs":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available"}
            max_attempts = int(os.getenv('CLAWUI_CDP_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_CDP_RETRY_DELAY', '1.0'))
            for attempt in range(max_attempts):
                try:
                    tabs = cdp.client.list_targets()
                    pages = [{"id": t.get("id"), "title": t.get("title", ""), "url": t.get("url", "")} for t in tabs if t.get("type") == "page"]
                    return {"type": "text", "text": json.dumps(pages, ensure_ascii=False)}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] cdp_list_tabs error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"CDP list_tabs failed after {max_attempts} attempts: {e}"}

        elif name == "cdp_new_tab":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available"}
            max_attempts = int(os.getenv('CLAWUI_CDP_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_CDP_RETRY_DELAY', '1.0'))
            url = input_data.get("url", "about:blank")
            for attempt in range(max_attempts):
                try:
                    result = cdp.client.new_tab(url)
                    return {"type": "text", "text": f"New tab: {json.dumps(result, ensure_ascii=False)[:300]}"}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] cdp_new_tab error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"CDP new_tab failed after {max_attempts} attempts: {e}"}

        elif name == "cdp_activate_tab":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available"}
            max_attempts = int(os.getenv('CLAWUI_CDP_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_CDP_RETRY_DELAY', '1.0'))
            for attempt in range(max_attempts):
                try:
                    ok = cdp.client.activate_tab(input_data["target_id"])
                    return {"type": "text", "text": f"Activated: {ok}"}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] cdp_activate_tab error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"CDP activate_tab failed after {max_attempts} attempts: {e}"}

        elif name == "cdp_close_tab":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available"}
            max_attempts = int(os.getenv('CLAWUI_CDP_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_CDP_RETRY_DELAY', '1.0'))
            for attempt in range(max_attempts):
                try:
                    ok = cdp.client.close_tab(input_data["target_id"])
                    return {"type": "text", "text": f"Closed: {ok}"}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] cdp_close_tab error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"CDP close_tab failed after {max_attempts} attempts: {e}"}

        elif name == "cdp_screenshot":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available"}
            max_attempts = int(os.getenv('CLAWUI_CDP_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_CDP_RETRY_DELAY', '1.0'))
            for attempt in range(max_attempts):
                try:
                    b64 = cdp.client.take_screenshot()
                    if b64:
                        return {"type": "image", "base64": b64}
                    raise Exception("Empty screenshot")
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] cdp_screenshot error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"CDP screenshot failed after {max_attempts} attempts: {e}"}

        # Marionette (Firefox) tools
        elif name == "ff_navigate":
            from .marionette_helper import get_or_create_marionette_client
            mc = get_or_create_marionette_client()
            if not mc:
                return {"type": "text", "text": "Marionette not available. Start Firefox with --marionette"}
            max_attempts = int(os.getenv('CLAWUI_MARIONETTE_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_MARIONETTE_RETRY_DELAY', '1.0'))
            for attempt in range(max_attempts):
                try:
                    mc.navigate(input_data["url"])
                    time.sleep(2)
                    info = {"url": mc.get_url(), "title": mc.get_title()}
                    return {"type": "text", "text": json.dumps(info, ensure_ascii=False)}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] ff_navigate error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"Firefox navigate failed after {max_attempts} attempts: {e}"}

        elif name == "ff_click":
            from .marionette_helper import get_or_create_marionette_client
            mc = get_or_create_marionette_client()
            if not mc:
                return {"type": "text", "text": "Marionette not available"}
            max_attempts = int(os.getenv('CLAWUI_MARIONETTE_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_MARIONETTE_RETRY_DELAY', '1.0'))
            for attempt in range(max_attempts):
                try:
                    el = mc.find_element("css selector", input_data["selector"])
                    if not el:
                        return {"type": "text", "text": "Element not found"}
                    ok = mc.click_element(el)
                    return {"type": "text", "text": f"Click: {ok}"}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] ff_click error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"Firefox click failed after {max_attempts} attempts: {e}"}

        elif name == "ff_type":
            from .marionette_helper import get_or_create_marionette_client
            mc = get_or_create_marionette_client()
            if not mc:
                return {"type": "text", "text": "Marionette not available"}
            max_attempts = int(os.getenv('CLAWUI_MARIONETTE_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_MARIONETTE_RETRY_DELAY', '1.0'))
            for attempt in range(max_attempts):
                try:
                    el = mc.find_element("css selector", input_data["selector"])
                    if not el:
                        return {"type": "text", "text": "Element not found"}
                    mc.send_keys(el, input_data["text"])
                    return {"type": "text", "text": f"Typed into {input_data['selector']}"}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] ff_type error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"Firefox type failed after {max_attempts} attempts: {e}"}

        elif name == "ff_eval":
            from .marionette_helper import get_or_create_marionette_client
            mc = get_or_create_marionette_client()
            if not mc:
                return {"type": "text", "text": "Marionette not available"}
            max_attempts = int(os.getenv('CLAWUI_MARIONETTE_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_MARIONETTE_RETRY_DELAY', '1.0'))
            for attempt in range(max_attempts):
                try:
                    result = mc.execute_script(input_data["script"])
                    return {"type": "text", "text": json.dumps(result, ensure_ascii=False)[:500]}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] ff_eval error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"Firefox eval failed after {max_attempts} attempts: {e}"}

        elif name == "ff_page_info":
            from .marionette_helper import get_or_create_marionette_client
            mc = get_or_create_marionette_client()
            if not mc:
                return {"type": "text", "text": "Marionette not available"}
            max_attempts = int(os.getenv('CLAWUI_MARIONETTE_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_MARIONETTE_RETRY_DELAY', '1.0'))
            for attempt in range(max_attempts):
                try:
                    info = {"url": mc.get_url(), "title": mc.get_title()}
                    return {"type": "text", "text": json.dumps(info, ensure_ascii=False)}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] ff_page_info error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"Firefox page_info failed after {max_attempts} attempts: {e}"}

        elif name == "ff_screenshot":
            from .marionette_helper import get_or_create_marionette_client
            mc = get_or_create_marionette_client()
            if not mc:
                return {"type": "text", "text": "Marionette not available"}
            max_attempts = int(os.getenv('CLAWUI_MARIONETTE_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_MARIONETTE_RETRY_DELAY', '1.0'))
            for attempt in range(max_attempts):
                try:
                    b64 = mc.take_screenshot()
                    if b64:
                        return {"type": "image", "base64": b64}
                    raise Exception("Empty screenshot")
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] ff_screenshot error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"Firefox screenshot failed after {max_attempts} attempts: {e}"}

        elif name == "ff_list_tabs":
            from .marionette_helper import get_or_create_marionette_client
            mc = get_or_create_marionette_client()
            if not mc:
                return {"type": "text", "text": "Marionette not available"}
            max_attempts = int(os.getenv('CLAWUI_MARIONETTE_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_MARIONETTE_RETRY_DELAY', '1.0'))
            for attempt in range(max_attempts):
                try:
                    handles = mc.get_window_handles()
                    return {"type": "text", "text": json.dumps(handles, ensure_ascii=False)}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] ff_list_tabs error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"Firefox list_tabs failed after {max_attempts} attempts: {e}"}

        elif name == "ff_switch_tab":
            from .marionette_helper import get_or_create_marionette_client
            mc = get_or_create_marionette_client()
            if not mc:
                return {"type": "text", "text": "Marionette not available"}
            max_attempts = int(os.getenv('CLAWUI_MARIONETTE_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_MARIONETTE_RETRY_DELAY', '1.0'))
            for attempt in range(max_attempts):
                try:
                    ok = mc.switch_to_window(input_data["handle"])
                    return {"type": "text", "text": f"Switched: {ok}"}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] ff_switch_tab error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"Firefox switch_tab failed after {max_attempts} attempts: {e}"}

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
            _recorder.start(
                name=input_data.get("name", ""),
                description=input_data.get("description", ""),
            )
            return {"type": "text", "text": f"Recording started: {_recorder.metadata['name']}"}

        elif name == "record_stop":
            script = _recorder.stop()
            rec_dir = os.path.join(os.path.dirname(__file__), "..", "recordings")
            filepath = input_data.get("filepath") or os.path.join(rec_dir, f"{script['metadata']['name']}.json")
            saved = _recorder.save(filepath)
            return {"type": "text", "text": f"Recording saved: {saved} ({len(script['actions'])} actions)"}

        elif name == "replay":
            player = ActionPlayer(execute_fn=execute_tool)
            script = player.load(input_data["filepath"])
            speed = input_data.get("speed", 1.0)
            dry_run = input_data.get("dry_run", False)
            results = player.replay(script, speed=speed, dry_run=dry_run)
            summary = f"Replayed {len(results)} actions"
            errors = [r for r in results if r["result"].get("type") == "error"]
            if errors:
                summary += f" ({len(errors)} errors)"
            return {"type": "text", "text": summary}

        elif name == "list_recordings":
            recs = list_recordings()
            if not recs:
                return {"type": "text", "text": "No recordings found"}
            lines = [f"- {r['name']}: {r['actions']} actions ({r['created']})" for r in recs]
            return {"type": "text", "text": "\n".join(lines)}

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

        else:
            return {"type": "text", "text": f"Unknown tool: {name}"}

    except Exception as e:
        return {"type": "text", "text": f"Error: {e}"}


def run_agent(task: str, max_steps: int = 30, model: str = "claude-sonnet-4-20250514"):
    """
    Run the GUI automation agent for a given task.
    
    Args:
        task: Natural language description of what to do
        max_steps: Maximum number of tool-use steps
        model: AI model to use
    """
    backend = get_backend(model)
    tools = create_tools()

    # Initial context: provide UI tree + active window
    active = get_active_window()
    apps = list_applications()
    initial_context = f"Active window: {active['name']}\nRunning apps: {', '.join(apps)}\n\nTask: {task}"

    messages = [{"role": "user", "content": initial_context}]
    consecutive_errors = 0
    last_response = None

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
            if consecutive_errors >= 3:
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
            break

        # Execute tools
        tool_results = []
        for tool_use in tool_uses:
            tool_result = execute_tool(tool_use.name, tool_use.input)

            if tool_result["type"] == "image":
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
            else:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": tool_result.get("text", str(tool_result)),
                })

        messages.append({"role": "user", "content": tool_results})

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
