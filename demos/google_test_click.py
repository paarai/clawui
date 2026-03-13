#!/usr/bin/env python3
"""
Test Google signup with improved click method.
"""

import sys
import os
import time
import base64

sys.path.insert(0, 'skills/gui-automation/src')
from cdp_helper import get_or_create_cdp_client

def click_next(cdp):
    find_script = """
    (function() {
      const btns = Array.from(document.querySelectorAll('button, [role="button"], a[href]'));
      const next = btns.find(b => {
        const txt = b.textContent.trim().toLowerCase();
        return txt.includes('next') || txt.includes('继续') || txt.includes('下一步');
      });
      if (next) {
        const rect = next.getBoundingClientRect();
        return {x: rect.x + rect.width/2, y: rect.y + rect.height/2, text: next.textContent.trim()};
      }
      return null;
    })()
    """
    res = cdp.evaluate(find_script)
    if res and 'x' in res:
        x, y = int(res['x']), int(res['y'])
        print(f"Clicking Next at ({x},{y}) text: '{res.get('text')}'")
        cdp.dispatch_mouse(x, y)
        return True
    print("Next button not found")
    return False

def main():
    cdp = get_or_create_cdp_client()
    if not cdp:
        print("Failed to start/connect CDP")
        return

    print("Navigating to accounts.google.com/signup...")
    cdp.navigate("https://accounts.google.com/signup")
    time.sleep(4)

    # Check title
    title = cdp.get_page_title()
    print(f"Page title: {title}")

    # Fill first/last name
    print("Filling first name...")
    cdp.type_in_element("input[name='firstName']", "Test")
    print("Filling last name...")
    cdp.type_in_element("input[name='lastName']", "User")

    time.sleep(1)
    print("Clicking Next...")
    if not click_next(cdp):
        print("FAILED at first Next")
        return
    time.sleep(3)

    print("Test reached after first Next - SUCCESS!")
    cdp.take_screenshot_and_save("screenshots/google_test_after_next.png")
    print("Screenshot saved.")

if __name__ == "__main__":
    main()
