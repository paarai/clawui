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
        {"name": "find_element", "description": "Find UI elements", "input_schema": {"type": "object", "properties": {"role": {"type": "string"}, "name": {"type": "string"}}}},
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
            elements = find_elements(
                role=input_data.get("role"),
                name=input_data.get("name"),
            )
            text = "\n".join(str(e) for e in elements[:20])
            return {"type": "text", "text": text or "(no elements found)"}

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
            vb = VisionBackend()
            prompt = f"Locate the UI element that matches: '{description}'. Return JSON with x, y (center coordinates), and confidence (0-1)."
            try:
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
                return {"type": "text", "text": f"Vision response could not be parsed: {text}"}
            except Exception as e:
                return {"type": "text", "text": f"Vision error: {e}"}

        # CDP tools
        elif name == "cdp_navigate":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available. Start Chromium with --remote-debugging-port=9222"}
            cdp.navigate(input_data["url"])
            time.sleep(2)
            title = cdp.get_page_title()
            return {"type": "text", "text": f"Navigated to {input_data['url']} - Title: {title}"}

        elif name == "cdp_click":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available"}
            result = cdp.click_element(input_data["selector"])
            return {"type": "text", "text": f"Clicked '{input_data['selector']}': {result}"}

        elif name == "cdp_type":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available"}
            result = cdp.type_in_element(input_data["selector"], input_data["text"])
            return {"type": "text", "text": f"Typed into '{input_data['selector']}': {result}"}

        elif name == "cdp_eval":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available"}
            result = cdp.evaluate(input_data["expression"])
            return {"type": "text", "text": f"JS result: {json.dumps(result, ensure_ascii=False)[:500]}"}

        elif name == "cdp_page_info":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available"}
            info = {"url": cdp.get_page_url(), "title": cdp.get_page_title()}
            return {"type": "text", "text": json.dumps(info, ensure_ascii=False)}

        elif name == "cdp_click_at":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available"}
            cdp.dispatch_mouse(input_data["x"], input_data["y"])
            return {"type": "text", "text": f"Clicked at ({input_data['x']}, {input_data['y']})"}

        elif name == "cdp_list_tabs":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available"}
            tabs = cdp.client.list_targets()
            pages = [{"id": t.get("id"), "title": t.get("title", ""), "url": t.get("url", "")} for t in tabs if t.get("type") == "page"]
            return {"type": "text", "text": json.dumps(pages, ensure_ascii=False)}

        elif name == "cdp_new_tab":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available"}
            url = input_data.get("url", "about:blank")
            result = cdp.client.new_tab(url)
            return {"type": "text", "text": f"New tab: {json.dumps(result, ensure_ascii=False)[:300]}"}

        elif name == "cdp_activate_tab":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available"}
            ok = cdp.client.activate_tab(input_data["target_id"])
            return {"type": "text", "text": f"Activated: {ok}"}

        elif name == "cdp_close_tab":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available"}
            ok = cdp.client.close_tab(input_data["target_id"])
            return {"type": "text", "text": f"Closed: {ok}"}

        elif name == "cdp_screenshot":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available"}
            b64 = cdp.client.take_screenshot()
            if b64:
                return {"type": "image", "base64": b64}
            return {"type": "text", "text": "Screenshot failed"}

        # Marionette (Firefox) tools
        elif name == "ff_navigate":
            from src.marionette_helper import get_or_create_marionette_client
            mc = get_or_create_marionette_client()
            if not mc:
                return {"type": "text", "text": "Marionette not available. Start Firefox with --marionette"}
            mc.navigate(input_data["url"])
            time.sleep(2)
            info = {"url": mc.get_url(), "title": mc.get_title()}
            return {"type": "text", "text": json.dumps(info, ensure_ascii=False)}

        elif name == "ff_click":
            from src.marionette_helper import get_or_create_marionette_client
            mc = get_or_create_marionette_client()
            if not mc:
                return {"type": "text", "text": "Marionette not available"}
            el = mc.find_element("css selector", input_data["selector"])
            if not el:
                return {"type": "text", "text": "Element not found"}
            ok = mc.click_element(el)
            return {"type": "text", "text": f"Click: {ok}"}

        elif name == "ff_type":
            from src.marionette_helper import get_or_create_marionette_client
            mc = get_or_create_marionette_client()
            if not mc:
                return {"type": "text", "text": "Marionette not available"}
            el = mc.find_element("css selector", input_data["selector"])
            if not el:
                return {"type": "text", "text": "Element not found"}
            mc.send_keys(el, input_data["text"])
            return {"type": "text", "text": f"Typed into {input_data['selector']}"}

        elif name == "ff_eval":
            from src.marionette_helper import get_or_create_marionette_client
            mc = get_or_create_marionette_client()
            if not mc:
                return {"type": "text", "text": "Marionette not available"}
            result = mc.execute_script(input_data["script"])
            return {"type": "text", "text": json.dumps(result, ensure_ascii=False)[:500]}

        elif name == "ff_page_info":
            from src.marionette_helper import get_or_create_marionette_client
            mc = get_or_create_marionette_client()
            if not mc:
                return {"type": "text", "text": "Marionette not available"}
            info = {"url": mc.get_url(), "title": mc.get_title()}
            return {"type": "text", "text": json.dumps(info, ensure_ascii=False)}

        elif name == "ff_screenshot":
            from src.marionette_helper import get_or_create_marionette_client
            mc = get_or_create_marionette_client()
            if not mc:
                return {"type": "text", "text": "Marionette not available"}
            b64 = mc.take_screenshot()
            if b64:
                return {"type": "image", "base64": b64}
            return {"type": "text", "text": "Screenshot failed"}

        elif name == "ff_list_tabs":
            from src.marionette_helper import get_or_create_marionette_client
            mc = get_or_create_marionette_client()
            if not mc:
                return {"type": "text", "text": "Marionette not available"}
            handles = mc.get_window_handles()
            return {"type": "text", "text": json.dumps(handles, ensure_ascii=False)}

        elif name == "ff_switch_tab":
            from src.marionette_helper import get_or_create_marionette_client
            mc = get_or_create_marionette_client()
            if not mc:
                return {"type": "text", "text": "Marionette not available"}
            ok = mc.switch_to_window(input_data["handle"])
            return {"type": "text", "text": f"Switched: {ok}"}

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

    for step in range(max_steps):
        print(f"\n--- Step {step + 1}/{max_steps} ---")

        consecutive_errors = 0
        try:
            result = backend.chat(
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
            # Add error context and retry
            messages.append({"role": "user", "content": f"[System] Backend error occurred: {e}. Please retry."})
            continue

        # Process response
        assistant_content = []
        tool_uses = []

        for block in result["raw_content"]:
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
            result = execute_tool(tool_use.name, tool_use.input)

            if result["type"] == "image":
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": [{
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": result["base64"],
                        }
                    }],
                })
            else:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result["text"],
                })

        messages.append({"role": "user", "content": tool_results})

    # Extract final text from last response
    if result.get("text"):
        return result["text"]
    return "Task completed."


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m src.agent 'Open Firefox and go to google.com'")
        sys.exit(1)
    result = run_agent(" ".join(sys.argv[1:]))
    print(f"\nResult: {result}")
