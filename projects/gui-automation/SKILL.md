---
name: gui-automation
description: "AI-driven GUI automation for Linux desktop. Control applications, click buttons, type text, and navigate UIs using natural language. Uses AT-SPI accessibility API + screenshot hybrid mode. Designed to be driven by the OpenClaw agent directly — no external AI API needed."
metadata:
  openclaw:
    requires:
      bins: ["xdotool", "gnome-screenshot"]
      python: ["pyatspi"]
---

# GUI Automation Skill

Control your Linux desktop through natural language commands. The OpenClaw agent (you) acts as the AI brain — perceiving the screen, making decisions, and executing actions.

## How It Works

You (the agent) are the decision loop:
1. **Perceive** — use `ui_tree` or `screenshot` to see the screen
2. **Decide** — figure out what to click/type/do
3. **Act** — call the action tools
4. **Verify** — check the result

No external AI API is needed. You ARE the AI.

## Tools Reference

### Perception

```bash
# List running GUI applications
cd ~/projects/gui-automation && python3 -m src.main apps

# Get UI element tree (structural — fast, precise)
python3 -m src.main tree                    # all apps
python3 -m src.main tree --app "firefox"    # specific app

# Take a screenshot (visual — for when AT-SPI isn't enough)
python3 -m src.main screenshot -o /tmp/screen.png
```

### Python API (for direct use in exec)

```python
import sys; sys.path.insert(0, '/home/hung/.openclaw/workspace/projects/gui-automation')

# --- Perception ---
from src.atspi_helper import list_applications, find_elements, get_ui_tree_summary, do_action, set_text
apps = list_applications()                          # ['firefox', 'nautilus', ...]
tree = get_ui_tree_summary("firefox", max_depth=5)  # structured UI tree with coordinates
btns = find_elements(role="push button", name="Save")  # find specific elements

from src.screenshot import take_screenshot
img_b64 = take_screenshot()  # base64 PNG — send to read() as image for visual analysis

# --- Actions ---
from src.actions import click, double_click, right_click, type_text, press_key, scroll, drag, mouse_move, focus_window

click(100, 200)                    # left click at coordinates
click(100, 200, button="right")    # right click
double_click(100, 200)
type_text("hello world")           # type text
press_key("Return")                # press key
press_key("ctrl+c")                # key combo
scroll("down", amount=5)
drag(100, 100, 300, 300)
focus_window(name="Firefox")

# --- AT-SPI Direct Actions (no coordinates needed) ---
elements = find_elements(role="push button", name="OK")
if elements:
    do_action(elements[0], "click")     # click via accessibility API
    # or: set_text(elements[0], "new text")  # set text in editable fields
```

## Strategy Guide

### When to use AT-SPI vs Screenshot:
- **AT-SPI first**: Fast, precise, gives you element names/roles/coordinates. Use for buttons, menus, text fields.
- **Screenshot when**: AT-SPI tree is empty/unhelpful, app doesn't support accessibility, or you need visual context.

### Common Patterns:

**Open an app:**
```python
import subprocess
subprocess.Popen(["firefox"], start_new_session=True)
import time; time.sleep(2)
```

**Find and click a button:**
```python
btns = find_elements(role="push button", name="Save")
if btns:
    do_action(btns[0], "click")  # AT-SPI click (most reliable)
else:
    # Fallback: screenshot → find visually → click coordinates
    click(x, y)
```

**Type in a text field:**
```python
fields = find_elements(role="text", name="Search")
if fields:
    set_text(fields[0], "my query")
    press_key("Return")
```

## Environment

- Session type: Wayland (GNOME) with XWayland
- Screenshot: gnome-screenshot
- Input: ydotool (Wayland native) + xdotool (XWayland fallback)
- AT-SPI: python3-pyatspi, gir1.2-atspi-2.0

## Extending with Other AI Backends

The `src/backends.py` module supports multiple AI backends for autonomous mode (when you want the agent to run independently without OpenClaw driving it):

- `AnyRouterBackend` — OpenClaw's built-in (requires internal access)
- `ClaudeBackend` — Anthropic API
- `OpenAIBackend` — GPT-4o
- `GeminiBackend` — Google Gemini
- `OllamaBackend` — Local models

Set `GUI_AI_MODEL=<model>` env var to select backend for autonomous mode:
```bash
GUI_AI_MODEL=llava:7b python3 -m src.main run "Open Firefox"
```
