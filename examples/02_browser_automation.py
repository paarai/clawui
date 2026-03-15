#!/usr/bin/env python3
"""ClawUI Example: Browser Automation via CDP

Prerequisites:
    Launch Chromium/Chrome with: --remote-debugging-port=9222
    Or use: clawui browser --url https://example.com

Demonstrates: navigation, form filling, text extraction, screenshots.
"""

from clawui.api import browser

# Connect (auto-connects to localhost:9222)
browser.connect(port=9222)

# Navigate
browser.navigate("https://httpbin.org/forms/post")
print(f"Page: {browser.get_title()}")
print(f"URL:  {browser.get_url()}")

# Fill a form
browser.type_into('input[name="custname"]', "ClawUI Test")
browser.type_into('textarea[name="comments"]', "Automated by ClawUI!")

# Click submit
browser.click_selector('button[type="submit"]')

# Wait for result page
if browser.wait_for("pre", timeout=5):
    print("\nResponse:")
    print(browser.get_text("pre")[:500])

# Take browser screenshot
browser.screenshot(save_to="browser_result.png")
print("\nScreenshot saved to browser_result.png")

# List tabs
tabs = browser.tabs()
print(f"\nOpen tabs: {len(tabs)}")
for t in tabs[:3]:
    print(f"  - {t.get('title', 'untitled')}")

browser.close()
