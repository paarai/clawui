#!/usr/bin/env python3
"""
Firefox Marionette Automation Demo.
Assumes Firefox is running with Marionette enabled:
firefox --marionette --headless
"""
import os, sys, time, base64
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.marionette_helper import MarionetteClient

def main():
    sdir = "screenshots/firefox_demo"
    os.makedirs(sdir, exist_ok=True)
    def snap(name):
        b64 = client.take_screenshot()
        if b64:
            with open(f"{sdir}/{name}.png", "wb") as f:
                f.write(base64.b64decode(b64))
            print(f"[snap] {name}")

    print("Connecting to Firefox Marionette...")
    client = MarionetteClient()
    if not client.is_available():
        print("ERROR: Marionette not available on port 2828.")
        print("Please start Firefox first: firefox --marionette --headless")
        return

    print("Connection successful. Navigating...")
    client.new_session()
    client.navigate("https://the-internet.herokuapp.com/login")
    time.sleep(3)
    snap("ff_login_page")

    print("Filling credentials...")
    user_el = client.find_element("css selector", "input#username")
    pwd_el = client.find_element("css selector", "input#password")
    if not user_el or not pwd_el:
        print("ERROR: Could not find username/password fields.")
        return

    client.send_keys(user_el, "tomsmith")
    client.send_keys(pwd_el, "SuperSecretPassword!")
    snap("ff_filled")

    print("Submitting login...")
    btn = client.find_element("css selector", "button[type='submit']")
    client.click_element(btn)
    time.sleep(3)
    snap("ff_after_login")

    # Check for success
    page_text = client.execute_script("return document.body.innerText")
    if page_text and "Secure Area" in page_text:
        print("Login successful!")
        logout_btn = client.find_element("css selector", 'a[href="/logout"]')
        if logout_btn:
            client.click_element(logout_btn)
            time.sleep(2)
            snap("ff_logout")
            print("Logged out.")
    else:
        print("Login failed or unexpected page.")
        print("Page text (first 200 chars):", str(page_text)[:200])

    client.close()
    print("=== Demo finished ===")

if __name__ == "__main__":
    main()
