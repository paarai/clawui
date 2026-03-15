#!/usr/bin/env python3
"""ClawUI Example: Drag & Drop, Window Management

Demonstrates: drag, right_click, hotkey, focus/minimize/maximize.
"""

from clawui.api import (
    drag, right_click, hotkey, move_mouse,
    focus_window, minimize, maximize, close,
    active_window, screenshot,
)

# Show current window
print(f"Active window: {active_window()['name']}")

# Right-click on desktop (opens context menu on many DEs)
# right_click(coords=(500, 400))

# Drag example: move something from (100,200) to (400,200)
# drag(start=(100, 200), end=(400, 200))

# Hotkey: open terminal (common on GNOME)
# hotkey("ctrl", "alt", "t")

# Window management
# minimize()       # Minimize active window
# maximize()       # Maximize active window
# focus_window(name="Firefox")  # Focus by name

print("Window management functions available:")
print("  drag(start, end)     - Drag and drop")
print("  right_click(coords)  - Right click")
print("  hotkey('ctrl', 's')  - Key combos")
print("  focus_window(name)   - Focus window")
print("  minimize/maximize()  - Window control")
