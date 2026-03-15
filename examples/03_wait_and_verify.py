#!/usr/bin/env python3
"""ClawUI Example: Waiting and Verification

Demonstrates: wait_for_element, wait_for_text, OCR, window management.
Useful for robust automation that handles timing/loading.
"""

from clawui.api import (
    wait_for_element, wait_for_text, ocr,
    windows, active_window, focus_window,
    click, press_key, screenshot,
)

# 1. List X11/XWayland windows
print("Windows:")
for w in windows()[:5]:
    print(f"  [{w.get('id')}] {w.get('name', '?')}")

# 2. Get active window info
aw = active_window()
print(f"\nActive: {aw['name']} (id={aw['id']})")

# 3. OCR the screen
print("\nOCR results (first 10 lines):")
lines = ocr()
for line in lines[:10]:
    print(f"  [{line.get('confidence', 0):.0f}%] {line['text']}")

# 4. Wait for an element (with timeout)
try:
    elem = wait_for_element(role="push button", name="OK", timeout=3)
    print(f"\nFound: {elem.name} at {elem.center}")
except TimeoutError:
    print("\nNo 'OK' button found (expected in this demo)")

# 5. Wait for text on screen via OCR
found = wait_for_text("Activities", timeout=3)
print(f"\n'Activities' visible on screen: {found}")
