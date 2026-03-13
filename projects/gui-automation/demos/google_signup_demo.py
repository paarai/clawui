#!/usr/bin/env python3
"""
Google Account Signup Automation Demo using CDP.
Demonstrates handling of complex forms and custom UI components.
Stops before phone verification to avoid creating real accounts.
"""

import os
import sys
import time
import random
import string
import base64

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cdp_helper import CDPClient

def random_username():
    return "testuser_" + ''.join(random.choices(string.digits, k=8))

def wait_for_navigation(cdp, timeout=10):
    """Wait for page navigation."""
    old_url = cdp.get_page_url()
    for _ in range(timeout):
        time.sleep(1)
        new_url = cdp.get_page_url()
        if new_url != old_url:
            return True
    return False

def click_next_button(cdp):
    """Click the 'Next' button using coordinate-based click for reliability."""
    # Try to find Next button text/position via JS
    find_script = """
    (function() {
      const btns = Array.from(document.querySelectorAll('button, [role="button"], a[href]'));
      const next = btns.find(b => {
        const txt = b.textContent.trim().toLowerCase();
        return txt.includes('next') || txt.includes('继续') || txt.includes('下一步');
      });
      if (next) {
        const rect = next.getBoundingClientRect();
        return {
          text: next.textContent.trim(),
          x: rect.x + rect.width / 2,
          y: rect.y + rect.height / 2,
          width: rect.width,
          height: rect.height
        };
      }
      return null;
    })()
    """
    result = cdp.evaluate(find_script)
    if result and isinstance(result, dict) and 'x' in result:
        x = int(result['x'])
        y = int(result['y'])
        print(f"  Found Next button: '{result.get('text')}' at ({x},{y}) size {result.get('width')}x{result.get('height')}")
        cdp.dispatch_mouse(x, y)
        return True
    else:
        print("  ERROR: Could not locate Next button")
        # Dump some info for debugging
        debug = cdp.evaluate("Array.from(document.querySelectorAll('button')).map(b=>({text:b.textContent.trim(), count:b.childElementCount})).slice(0,5)")
        print(f"  Debug: first 5 buttons: {debug}")
        return False

def main():
    cdp = CDPClient()
    print("=== Google Signup Automation Demo ===")
    username = random_username()
    password = "Test1234!"
    first = "Test"
    last = "User"
    year = "1990"
    month_text = "January"  # will click by visible text
    gender = "Male"

    screens_dir = "screenshots/google_demo"
    import os
    os.makedirs(screens_dir, exist_ok=True)

    def screenshot(step):
        b64 = cdp.take_screenshot()
        if b64:
            path = f"{screens_dir}/step_{step}.png"
            with open(path, "wb") as f:
                f.write(base64.b64decode(b64))
            print(f"Screenshot saved: {path}")

    # Step 1: Navigate to signup
    print("Navigating to Google signup...")
    cdp.navigate("https://accounts.google.com/signup")
    time.sleep(3)
    screenshot(1)

    # Step 2: Name
    print("Filling name...")
    cdp.type_in_element("input[name='firstName']", first)
    cdp.type_in_element("input[name='lastName']", last)
    if not click_next_button(cdp):
        print("ERROR: Could not click Next on name page")
        return
    time.sleep(3)
    screenshot(2)

    # Step 3: Birthday & Gender
    print("Filling birthday and gender...")
    # Year (standard input)
    cdp.type_in_element("input[name='year']", year)
    # Month: custom dropdown; click the month selector, then pick month by text
    # Try to click the month dropdown via aria-label
    month_dropdown = "div[aria-label*='Month' i]"
    if not cdp.click_element(month_dropdown):
        cdp.evaluate("document.querySelector('[aria-label*=\"Month\" i]')?.click()")
        print("Clicked month dropdown via JS")
    time.sleep(1)
    # Select month option
    month_js = f"""
    const options = Array.from(document.querySelectorAll('div[role="option"], div[aria-label*="month" i], span[role="option"]'));
    const opt = options.find(e => e.textContent.trim() === '{month_text}');
    if (opt) {{ opt.click(); return true; }}
    return false;
    """
    if not cdp.evaluate(month_js):
        print(f"WARNING: Could not select month {month_text}")
    time.sleep(1)
    # Gender: click the radio corresponding to 'Male'
    gender_js = """
    const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
    const male = radios.find(r => r.value.toLowerCase().includes('male') || r.getAttribute('aria-label')?.toLowerCase().includes('male'));
    if (male) { male.click(); return true; }
    return false;
    """
    if not cdp.evaluate(gender_js):
        print("WARNING: Could not select gender Male")
    time.sleep(1)
    if not click_next_button(cdp):
        print("ERROR: Could not click Next on birthday page")
        return
    time.sleep(3)
    screenshot(3)

    # Step 4: Choose username
    print(f"Entering username: {username}")
    cdp.type_in_element("input[name='username']", username)
    if not click_next_button(cdp):
        print("ERROR: Could not click Next on username page")
        return
    time.sleep(3)
    screenshot(4)

    # Step 5: Password
    print("Entering password...")
    cdp.type_in_element("input[name='Passwd']", password)
    time.sleep(1)
    cdp.type_in_element("input[name='PasswdAgain']", password)
    if not click_next_button(cdp):
        print("ERROR: Could not click Next on password page")
        return
    time.sleep(3)
    screenshot(5)

    print("Reached phone verification step (or final).")
    print("Demo stops here to avoid creating a real account.")
    screenshot(6)
    print(f"Test username that would be used: {username}")
    print("Automation completed successfully up to phone verification.")

if __name__ == "__main__":
    import base64
    main()
