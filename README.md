# GUI Automation Skill for OpenClaw

AI-driven GUI automation for Linux desktop. Control applications, click buttons, type text, and navigate UIs using natural language. This skill is designed to be driven by the OpenClaw agent directly — no external AI API is needed for its core functionality.

## Key Concept: Wayland vs. X11 Perception

Automating modern Linux desktops is complex due to the transition from X11 to Wayland. This skill implements a hybrid perception model to handle both.

- **The Problem**: Under a Wayland session, applications running via the **XWayland** compatibility layer (like Firefox, Chrome, VSCode, and many Electron apps) are not visible to the standard Accessibility Toolkit (AT-SPI). This makes them invisible to many automation tools.
- **The Solution**: This skill now includes a dual-backend perception system:
    1.  **`atspi_helper.py`**: Interacts with native Wayland applications (e.g., GNOME Settings, Files).
    2.  **`x11_helper.py`**: Interacts with XWayland applications using traditional X11 tools (`xdotool`).
- **`perception.py`**: This is the **recommended entry point**. It's a routing layer that automatically detects the application type and uses the correct backend, providing a unified view.

> **Recommendation for Best Results**: For the most reliable and comprehensive automation, **log into a native X11 session** on your desktop. This makes *all* applications visible to the X11 backend, bypassing Wayland's security sandboxing.

## Features

- **Hybrid Perception**: Automatically uses AT-SPI for Wayland-native apps and an X11 backend for XWayland apps.
- **Unified API**: The `perception.py` module provides simple, high-level functions (`find_elements`, `do_action`, etc.) that work across both backends.
- **Actions**: Mouse clicks, keyboard input, scrolling, dragging, window focus.
- **Multi-backend**: Supports external AI models (Claude, GPT-4o, etc.) for optional autonomous operation.
- **OpenClaw-native**: The agent acts as the AI brain by default.

## Requirements

- **OS**: Linux (tested on Ubuntu 24.04). An **X11 session is highly recommended**.
- **Python packages**: `pyatspi` (`python3-pyatspi`), `gir1.2-atspi-2.0`, `python-xlib`.
- **CLI tools**: `xdotool`, `gnome-screenshot`.

## Quick Start

The skill is located in `~/.openclaw/workspace/skills/gui-automation/`.

### From the command line

```bash
cd ~/.openclaw/workspace/skills/gui-automation

# List all running GUI applications (from both Wayland and X11)
python3 -m src.main apps

# Get a combined UI tree (shows AT-SPI and X11 trees)
python3 -m src.main tree
```

### From Python (Recommended Method)

Use the `perception` module for robust, backend-agnostic automation.

```python
import sys
sys.path.insert(0, '/home/hung/.openclaw/workspace/skills/gui-automation')

# Use the perception module as the main entry point
from src.perception import list_applications, find_elements, get_ui_tree_summary, do_action, set_text
from src.actions import click, type_text, press_key # General actions are still useful

# List all visible apps
apps = list_applications()
print(f"Found apps: {apps}")

# Get a combined UI tree
tree = get_ui_tree_summary()
print(tree)

# Find a button in a Wayland-native app (like GNOME settings)
power_off_button = find_elements(app_name="gnome-control-center", role="push button", name="Power Off…")
if power_off_button:
    print("Found power off button via AT-SPI.")
    # do_action(power_off_button[0], "click") # This would click it

# Find a window in an XWayland app (like Firefox)
firefox_window = find_elements(app_name="firefox", name="Mozilla Firefox")
if firefox_window:
    print(f"Found Firefox window via X11: {firefox_window[0].title}")
    # do_action(firefox_window[0], "activate") # This would focus it

# Type text (uses the X11 backend, which is usually globally effective)
# type_text("This works globally!")
# press_key("Return")
```

## Workflow Examples

The following examples have been updated to use the `perception` module for better compatibility.

### Example 1: Save a Text File in Gedit (Wayland Native)

```python
import sys
import subprocess
import time

sys.path.insert(0, '/home/hung/.openclaw/workspace/skills/gui-automation')

from src.perception import find_elements, do_action, set_text
from src.actions import type_text, press_key

# ... (rest of the Gedit example code, now using perception functions)
# Note: This example works best with native Wayland apps.
```

### Example 2: Use GNOME Calculator (Wayland Native)

```python
import sys
import subprocess
import time

sys.path.insert(0, '/home/hung/.openclaw/workspace/skills/gui-automation')

from src.perception import find_elements, do_action

# ... (rest of the Calculator example code, now using perception functions)
```

## Autonomous Mode (Optional)

(Content unchanged)

## Project Structure

- **`src/perception.py`**: **Main entry point.** Routes to the correct backend.
- `src/atspi_helper.py`: Backend for native Wayland apps.
- `src/x11_helper.py`: Backend for X11/XWayland apps.
- `src/actions.py`: Low-level input operations.
- `src/main.py`: CLI entrypoint.

For full reference, see `SKILL.md`.
