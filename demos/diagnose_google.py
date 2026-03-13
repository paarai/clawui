#!/usr/bin/env python3
import sys, os, time
sys.path.insert(0, 'skills/gui-automation/src')
from cdp_helper import get_or_create_cdp_client

cdp = get_or_create_cdp_client()
if not cdp:
    print("CDP not available")
    exit(1)

print("Navigating to Google signup...")
cdp.navigate("https://accounts.google.com/signup")
time.sleep(5)

title = cdp.get_page_url()
print("Current URL:", title)

# Get all buttons as plain text
buttons_js = """
(() => {
  const btns = Array.from(document.querySelectorAll('button'));
  return btns.map(b => ({
    text: b.textContent.trim(),
    disabled: b.disabled,
    type: b.type,
    name: b.name,
    id: b.id
  }));
})()
"""
buttons = cdp.evaluate(buttons_js)
import json
print("Buttons found:", json.dumps(buttons, indent=2)[:2000])

# Save screenshot
b64 = cdp.take_screenshot()
if b64:
    with open("screenshots/google_diagnose.png", "wb") as f:
        f.write(b64)
    print("Screenshot saved to screenshots/google_diagnose.png")
