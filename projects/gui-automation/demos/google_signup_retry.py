#!/usr/bin/env python3
"""Google signup retry with adjusted phone format and user-specified password."""
import os, sys, time, base64
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.cdp_helper import CDPClient

def click_next(cdp):
    for sel in ["button[jsname='Cuz2Ue']", "button[type='submit']"]:
        try:
            if cdp.click_element(sel): return True
        except: pass
    return cdp.evaluate("""
        const b = Array.from(document.querySelectorAll('button')).find(b => /Next|下一步/.test(b.textContent));
        if(b){b.click();return true;} return false;
    """) is True

def main():
    cdp = CDPClient()
    sdir = "screenshots/google_signup_retry"
    os.makedirs(sdir, exist_ok=True)

    def snap(n):
        b = cdp.take_screenshot()
        if b:
            with open(f"{sdir}/step_{n}.png","wb") as f: f.write(base64.b64decode(b))
            print(f"Screenshot: step_{n}.png")

    print("=== Google Signup Retry ===")
    # Step 1: Navigate
    cdp.navigate("https://accounts.google.com/signup")
    time.sleep(4)
    snap(1)

    # Step 2: Name
    print("Filling name...")
    cdp.type_in_element("input[name='firstName']", "Test")
    cdp.type_in_element("input[name='lastName']", "User")
    click_next(cdp); time.sleep(4); snap(2)

    # Step 3: Birthday/Gender
    print("Filling birthday/gender...")
    # Day first (some layouts show day field)
    cdp.type_in_element("input[name='day']", "15")
    cdp.type_in_element("input[name='year']", "1990")
    # Month dropdown
    cdp.evaluate("document.querySelector('#month')?.click()")
    time.sleep(1)
    cdp.evaluate("""
        const opts = document.querySelectorAll('#month option');
        if(opts.length > 1) { opts[1].selected = true;
            document.querySelector('#month').dispatchEvent(new Event('change', {bubbles:true})); }
    """)
    time.sleep(1)
    # Gender dropdown
    cdp.evaluate("document.querySelector('#gender')?.click()")
    time.sleep(1)
    cdp.evaluate("""
        const opts = document.querySelectorAll('#gender option');
        if(opts.length > 1) { opts[1].selected = true;
            document.querySelector('#gender').dispatchEvent(new Event('change', {bubbles:true})); }
    """)
    time.sleep(1)
    click_next(cdp); time.sleep(4); snap(3)

    # Step 4: Username
    print("Entering username: longgo1002")
    cdp.type_in_element("input[name='username']", "longgo1002")
    click_next(cdp); time.sleep(4); snap(4)

    # Step 5: Password (user specified)
    print("Entering password...")
    cdp.type_in_element("input[name='Passwd']", ":0987654321.")
    cdp.type_in_element("input[name='PasswdAgain']", ":0987654321.")
    click_next(cdp); time.sleep(5); snap(5)

    # Step 6: Phone - try pure digits without +1
    print("Entering phone: 2563335672")
    cdp.type_in_element("input[type='tel'], input#phoneNumberId", "2563335672")
    time.sleep(1)
    snap("6a")
    click_next(cdp); time.sleep(6); snap(6)

    # Step 7: Wait for SMS code
    print("WAITING_FOR_CODE")
    sys.stdout.flush()
    code = input()
    print(f"Entering code: {code}")
    cdp.type_in_element("input[type='tel'], input#code, input[aria-label*='code' i], input[aria-label*='验证' i]", code.strip())
    time.sleep(1)
    click_next(cdp); time.sleep(5); snap(7)
    print("DONE")

if __name__ == "__main__":
    main()
