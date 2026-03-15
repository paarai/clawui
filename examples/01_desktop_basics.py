#!/usr/bin/env python3
"""ClawUI Example: Desktop Automation Basics

Demonstrates: screenshot, UI tree, finding elements, clicking, typing.
"""

from clawui.api import screenshot, apps, tree, find_elements, click, type_text, press_key

# 1. Take a screenshot
print("Taking screenshot...")
screenshot(save_to="desktop.png")
print("Saved to desktop.png")

# 2. List running applications
print("\nRunning apps:")
for app in apps():
    print(f"  - {app}")

# 3. Show UI tree (top-level)
print("\nUI Tree (depth=2):")
print(tree(max_depth=2))

# 4. Find all buttons on screen
buttons = find_elements(role="push button")
print(f"\nFound {len(buttons)} buttons:")
for b in buttons[:5]:
    print(f"  [{b.role}] {b.name}")

# 5. Click + Type example (uncomment to run)
# click(text="Files")           # Click by element name
# click(coords=(500, 300))      # Click by coordinates
# type_text("Hello from ClawUI!")
# press_key("Return")
