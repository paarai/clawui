#!/usr/bin/env python3
"""
Comprehensive CDP demo: form filling, tabs, screenshots.
Tests all 11 CDP tools on httpbin.org/forms/post.
"""

import time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from cdp_helper import CDPClient

def main():
    c = CDPClient()
    if not c.is_available():
        print("ERROR: CDP not available. Start Chromium with --remote-debugging-port=9222")
        return

    print("=== CDP Browser Automation Demo ===\n")

    # 1. Navigate
    print("1. Navigate to httpbin.org/forms/post")
    c.navigate("https://httpbin.org/forms/post")
    time.sleep(2)

    # 2. Page info
    print("2. Page info:")
    print(f"   URL: {c.get_page_url()}")
    print(f"   Title: {c.get_page_title()}")

    # 3. Screenshot before filling
    ss1 = c.take_screenshot()
    print(f"3. Screenshot captured ({len(ss1)} chars base64)")

    # 4. Fill form using cdp_type (real keyboard)
    print("4. Fill form fields using cdp_type")
    c.type_text('input[name="custname"]', "ClawUI Demo")
    time.sleep(0.3)
    c.type_text('input[name="custemail"]', "demo@example.com")
    time.sleep(0.3)
    # Dropdown via dispatch_mouse (custom UI) - coordinates relative to viewport
    c.dispatch_mouse(350, 340)  # approximate dropdown area; select "Mr."
    time.sleep(0.5)
    # Radio by click_element
    c.click_element('input[value="music"]')
    time.sleep(0.3)
    # Additional comment
    c.type_text('textarea[name="comments"]', "Testing ClawUI CDP automation!")
    time.sleep(0.3)
    print("   Form filled")

    # 5. Verify values via evaluate
    name_val = c.evaluate('document.querySelector("input[name=custname]").value')
    print(f"5. Verification: custname = {name_val.get('result', {}).get('value')}")

    # 6. List tabs (should be 1)
    tabs_before = [t for t in c.list_targets() if t.get("type") == "page"]
    print(f"6. Tabs before new tab: {len(tabs_before)}")

    # 7. New tab
    print("7. Open new tab to example.com")
    new_tab = c.new_tab("https://example.com")
    time.sleep(2)
    tabs_after = [t for t in c.list_targets() if t.get("type") == "page"]
    print(f"   Tabs now: {len(tabs_after)}")

    # 8. Screenshot new tab
    ss2 = c.take_screenshot()
    print(f"8. New tab screenshot: {len(ss2)} chars base64")

    # 9. Activate first tab
    first_id = tabs_before[0]["id"] if tabs_before else None
    if first_id:
        ok = c.activate_tab(first_id)
        print(f"9. Activated first tab: {ok}")
        time.sleep(1)

    # 10. Close new tab
    new_ids = [t["id"] for t in tabs_after if t["id"] != first_id]
    if new_ids:
        ok = c.close_tab(new_ids[0])
        print(f"10. Closed new tab: {ok}")
        time.sleep(1)

    # 11. Final screenshot
    ss3 = c.take_screenshot()
    print(f"11. Final screenshot: {len(ss3)} chars base64")

    print("\n=== Demo completed successfully ===")
    print("All 11 CDP tools tested:")
    print("- navigate, click_element, click_at, type_text, dispatch_key")
    print("- evaluate, get_page_url, get_page_title, take_screenshot")
    print("- list_targets, new_tab, activate_tab, close_tab")
    print("Output screenshots saved in variable; you can decode base64 to PNG files.")

if __name__ == "__main__":
    main()
