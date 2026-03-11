#!/usr/bin/env python3
"""
Simple login automation demo on the-internet.herokuapp.com.
Public test site: https://the-internet.herokuapp.com/login
Credentials: tomsmith / SuperSecretPassword!
"""

import os, sys, time, base64
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.cdp_helper import CDPClient

def main():
    cdp = CDPClient()
    sdir = "screenshots/simple_login"
    os.makedirs(sdir, exist_ok=True)
    def snap(name):
        b64 = cdp.take_screenshot()
        if b64:
            with open(f"{sdir}/{name}.png", "wb") as f:
                f.write(base64.b64decode(b64))
            print(f"[snap] {name}")

    url = "https://the-internet.herokuapp.com/login"
    print(f"[1] Navigate to {url}")
    cdp.navigate(url)
    time.sleep(3)
    snap("login_page")

    print("[2] Fill credentials")
    cdp.type_in_element('input#username', 'tomsmith')
    cdp.type_in_element('input#password', 'SuperSecretPassword!')
    snap("filled")

    print("[3] Click Login")
    cdp.click_element('button[type="submit"]')
    time.sleep(3)
    snap("after_login")

    # Check result
    page = cdp.evaluate('document.body.innerText')
    if page and 'Secure Area' in page:
        print("[4] Login successful - Secure Area confirmed")
        snap("success")
    else:
        print("[4] Login failed or unexpected page")
        snap("failure")

    print("[5] Logout (optional)")
    if cdp.click_element('a[href="/logout"]'):
        time.sleep(2)
        snap("logout")
        print("Logged out")
    else:
        print("Logout link not found")

    print("=== Demo finished ===")

if __name__ == "__main__":
    main()
