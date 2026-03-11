#!/usr/bin/env python3
"""
Google Account Signup Automation Demo (Interactive) using CDP.
This script automates the full Google signup flow, requiring user
to provide the SMS verification code when prompted.
"""

import os
import sys
import time
import base64

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cdp_helper import CDPClient

def click_next_button(cdp):
    """Click the 'Next' button using multiple strategies."""
    selectors = [
        "button[jsname='Cuz2Ue']",
        "button[type='submit']",
        "button:contains('Next')",
        "button:contains('下一步')",
    ]
    for sel in selectors:
        try:
            if cdp.click_element(sel):
                print(f"Clicked 'Next' using selector: {sel}")
                return True
        except Exception:
            pass
    script = """
    const btns = Array.from(document.querySelectorAll('button'));
    const next = btns.find(b => /Next|继续|下一步|继续下一步/.test(b.textContent.trim()));
    if (next) { next.click(); return true; }
    return false;
    """
    result = cdp.evaluate(script)
    if result:
        print("Clicked 'Next' using JavaScript fallback.")
    return result is True

def main(username, phone_number):
    cdp = CDPClient()
    print("=== Google Signup Interactive Demo ===")
    password = "TestPassword123!"
    first = "Test"
    last = "User"
    year = "1990"
    month_text = "January"
    gender = "Male"

    screens_dir = f"screenshots/google_signup_{username}"
    os.makedirs(screens_dir, exist_ok=True)

    def screenshot(step, name):
        b64 = cdp.take_screenshot()
        if b64:
            path = f"{screens_dir}/step_{step}_{name}.png"
            with open(path, "wb") as f:
                f.write(base64.b64decode(b64))
            print(f"Screenshot saved: {path}")

    # Step 1: Navigate
    print("Navigating to Google signup...")
    cdp.navigate("https://accounts.google.com/signup")
    time.sleep(3)
    screenshot(1, "navigate")

    # Step 2: Name
    print("Filling name...")
    cdp.type_in_element("input[name='firstName']", first)
    cdp.type_in_element("input[name='lastName']", last)
    if not click_next_button(cdp): return print("ERROR: Failed at Name page")
    time.sleep(3)
    screenshot(2, "name")

    # Step 3: Birthday & Gender
    print("Filling birthday and gender...")
    cdp.type_in_element("input[name='year']", year)
    cdp.click_element("div[aria-label*='Month' i]")
    time.sleep(1)
    cdp.evaluate(f"Array.from(document.querySelectorAll('div[role=\"option\"]')).find(e => e.textContent.trim() === '{month_text}').click()")
    time.sleep(1)
    cdp.evaluate(f"Array.from(document.querySelectorAll('input[type=\"radio\"]')).find(r => r.getAttribute('aria-label')?.toLowerCase().includes('{gender.lower()}')).click()")
    time.sleep(1)
    if not click_next_button(cdp): return print("ERROR: Failed at Birthday page")
    time.sleep(3)
    screenshot(3, "birthday")

    # Step 4: Username
    print(f"Entering username: {username}")
    cdp.type_in_element("input[name='username']", username)
    if not click_next_button(cdp): return print("ERROR: Failed at Username page")
    time.sleep(3)
    screenshot(4, "username")

    # Step 5: Password
    print("Entering password...")
    cdp.type_in_element("input[name='Passwd']", password)
    cdp.type_in_element("input[name='PasswdAgain']", password)
    if not click_next_button(cdp): return print("ERROR: Failed at Password page")
    time.sleep(5) # Wait for navigation to phone page
    screenshot(5, "password")

    # Step 6: Phone Verification
    print("Entering phone number...")
    # Google might auto-detect country and pre-fill, so we find the main input
    phone_input_selector = "input[type='tel'], input#phoneNumberId"
    cdp.type_in_element(phone_input_selector, phone_number.replace("+1", ""))
    time.sleep(1)
    if not click_next_button(cdp): return print("ERROR: Failed at Phone Number page")
    time.sleep(5) # Wait for SMS code page
    screenshot(6, "phone_number_entered")

    # Step 7: SMS Code Input
    print("PROMPT: Please enter the 6-digit SMS code sent to the phone.")
    sys.stdout.flush() # Ensure prompt is visible
    sms_code = input()
    
    print(f"Entering SMS code: {sms_code}")
    cdp.type_in_element("input[aria-label*='Enter the code' i], input#code", sms_code)
    time.sleep(1)
    if not click_next_button(cdp): return print("ERROR: Failed at SMS code page")
    time.sleep(5)
    screenshot(7, "sms_code_entered")
    
    print("Registration flow seems complete. Final page screenshot taken.")
    screenshot(8, "final_page")
    print("SUCCESS: Automation finished.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 demos/google_signup_interactive.py <username> <phone_number>")
        sys.exit(1)
    main(username=sys.argv[1], phone_number=sys.argv[2])
