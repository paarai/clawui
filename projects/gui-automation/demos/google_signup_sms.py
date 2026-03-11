#!/usr/bin/env python3
"""Google signup with online SMS platform number."""
import os, sys, time, base64
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.cdp_helper import CDPClient

def click_next(cdp):
    for sel in ["button[jsname='Cuz2Ue']", "button[type='submit']"]:
        try:
            if cdp.click_element(sel): return True
        except: pass
    return cdp.evaluate("""
        const b=Array.from(document.querySelectorAll('button')).find(b=>/Next|下一步/.test(b.textContent));
        if(b){b.click();return true;}return false;
    """) is True

def get_page_text(cdp):
    """Get visible text on page for debugging."""
    return cdp.evaluate("document.body?.innerText?.substring(0, 500)") or ""

def main():
    cdp = CDPClient()
    sdir = "screenshots/google_signup_sms"
    os.makedirs(sdir, exist_ok=True)
    def snap(n):
        b = cdp.take_screenshot()
        if b:
            with open(f"{sdir}/step_{n}.png","wb") as f: f.write(base64.b64decode(b))
            print(f"Screenshot: step_{n}.png")

    phone = "2812166971"  # from receive-smss.com
    username = "clawuitest2026"
    password = ":0987654321."

    print(f"=== Google Signup with SMS Platform ===")
    print(f"Phone: +1{phone}")
    print(f"Username: {username}")

    # Step 1
    cdp.navigate("https://accounts.google.com/signup")
    time.sleep(4); snap(1)

    # Step 2: Name
    print("Filling name...")
    cdp.type_in_element("input[name='firstName']", "Claw")
    cdp.type_in_element("input[name='lastName']", "Test")
    click_next(cdp); time.sleep(4); snap(2)
    print("Page text:", get_page_text(cdp)[:200])

    # Step 3: Birthday/Gender
    print("Filling birthday/gender...")
    cdp.type_in_element("input[name='day']", "15")
    cdp.type_in_element("input[name='year']", "1995")
    cdp.evaluate("""
        const m=document.querySelector('#month');
        if(m){m.value='1';m.dispatchEvent(new Event('change',{bubbles:true}));}
    """)
    time.sleep(1)
    cdp.evaluate("""
        const g=document.querySelector('#gender');
        if(g){g.value='1';g.dispatchEvent(new Event('change',{bubbles:true}));}
    """)
    time.sleep(1)
    click_next(cdp); time.sleep(4); snap(3)
    print("Page text:", get_page_text(cdp)[:200])

    # Step 4: Username
    print(f"Entering username: {username}")
    cdp.type_in_element("input[name='username']", username)
    click_next(cdp); time.sleep(4); snap(4)
    print("Page text:", get_page_text(cdp)[:200])

    # Step 5: Password
    print("Entering password...")
    cdp.type_in_element("input[name='Passwd']", password)
    cdp.type_in_element("input[name='PasswdAgain']", password)
    click_next(cdp); time.sleep(5); snap(5)
    print("Page text:", get_page_text(cdp)[:200])

    # Step 6: Phone
    print(f"Entering phone: {phone}")
    cdp.type_in_element("input[type='tel'], input#phoneNumberId", phone)
    time.sleep(1); snap("6a")
    click_next(cdp); time.sleep(8); snap(6)
    page_text = get_page_text(cdp)
    print("Page text:", page_text[:300])

    # Check if phone was rejected
    if "couldn't verify" in page_text.lower() or "无法验证" in page_text or "not be used" in page_text.lower():
        print("PHONE_REJECTED: Google rejected this phone number")
        return

    print("WAITING_FOR_CODE")
    sys.stdout.flush()
    code = input()
    print(f"Entering code: {code}")
    cdp.type_in_element("input[type='tel'], input#code, input[aria-label*='code' i]", code.strip())
    click_next(cdp); time.sleep(5); snap(7)
    print("DONE:", get_page_text(cdp)[:200])

if __name__ == "__main__":
    main()
