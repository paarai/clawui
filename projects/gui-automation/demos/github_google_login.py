#!/usr/bin/env python3
"""
Automate GitHub login using Google account.
Steps:
1. Go to GitHub login
2. Click "Continue with Google"
3. Enter Google email
4. Enter Google password
5. Handle OAuth consent (Authorize)
"""

import os, sys, time, base64
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.cdp_helper import CDPClient

def wait_for(condition, timeout=20):
    """Poll for a condition (function returning truthy) with timeout."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            if condition():
                return True
        except Exception:
            pass
        time.sleep(1)
    return False

def main():
    cdp = CDPClient()
    sdir = "screenshots/github_google_login"
    os.makedirs(sdir, exist_ok=True)
    def snap(name):
        b64 = cdp.take_screenshot()
        if b64:
            with open(f"{sdir}/{name}.png", "wb") as f:
                f.write(base64.b64decode(b64))
            print(f"[snap] {name}")

    # Configuration
    EMAIL = "longgo1001@gmail.com"
    PASSWORD = ":0987654321."

    # Step 1: GitHub login page
    print("[1] Navigate to GitHub login...")
    cdp.navigate("https://github.com/login")
    time.sleep(3)
    snap("github_login")

    # Step 2: Click "Continue with Google"
    print("[2] Click Continue with Google")
    # Use JS to find button with Google text
    cdp.evaluate('''
        var btns = Array.from(document.querySelectorAll('button'));
        var google = btns.find(b => b.textContent.includes('Google'));
        if (google) { google.click(); } else { console.log('Google button not found'); }
    ''')
    time.sleep(5)
    snap("after_google_click")

    # Step 3: Wait for Google sign-in page (email input)
    print("[3] Wait for Google email field")
    def email_visible():
        return cdp.evaluate('document.querySelector("input[type=\'email\'], input[name=\'identifier\']") != null')
    if not wait_for(email_visible, 15):
        print("ERROR: Email field never appeared")
        return
    snap("google_email_page")

    # Enter email
    print("[4] Enter email")
    cdp.type_in_element('input[type="email"], input[name="identifier"]', EMAIL)
    time.sleep(2)
    snap("email_entered")

    # Click Next (button with jsname LgbsSe and text "下一步" or "Next")
    print("[5] Click Next after email")
    next_js = '''
        var btns = Array.from(document.querySelectorAll('button'));
        var nxt = btns.find(b => /Next|下一步/.test(b.textContent));
        if (nxt) { nxt.click(); true; } else { false; }
    '''
    clicked = cdp.evaluate(next_js)
    print(f"Clicked: {clicked}")
    time.sleep(5)
    snap("after_email_next")

    # Step 6: Wait for password field
    print("[6] Wait for password field")
    def pwd_visible():
        return cdp.evaluate('document.querySelector("input[type=\'password\']") != null')
    if not wait_for(pwd_visible, 20):
        # Might be hidden due to 2FA/captcha; dump page
        page = cdp.evaluate('document.body.innerText.substring(0,1000)')
        print("Password field not found. Page snapshot:", str(page or '')[:500])
        snap("no_password")
        return
    snap("password_page")

    # Enter password
    print("[7] Enter password")
    cdp.type_in_element('input[type="password"], input[name="password"]', PASSWORD)
    time.sleep(2)
    snap("password_entered")

    # Click Next
    print("[8] Submit password")
    cdp.evaluate(next_js)
    time.sleep(8)
    snap("after_password_next")
    print("Current URL:", cdp.get_page_url())

    # Step 9: Maybe OAuth consent page
    print("[9] Check for OAuth consent")
    time.sleep(5)
    snap("final_state")
    page_text = cdp.evaluate('document.body.innerText.substring(0,1000)')
    print("Final page:", str(page_text or '')[:300])

    # Look for "Authorize" button and click
    auth_js = '''
        var btns = Array.from(document.querySelectorAll('button'));
        var auth = btns.find(b => /Authorize|授权|允许|确认/.test(b.textContent));
        if (auth) { auth.click(); true; } else { false; }
    '''
    if cdp.evaluate(auth_js):
        print("Clicked Authorize")
        time.sleep(5)
        snap("after_authorize")
        print("Final URL:", cdp.get_page_url())
    else:
        print("No Authorization button found (maybe already logged in)")

    print("=== Done ===")

if __name__ == "__main__":
    main()
