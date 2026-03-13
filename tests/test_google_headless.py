#!/usr/bin/env python3
"""
Test: Force headless Chromium and verify Google signup flow.
"""

import sys, os, time
sys.path.insert(0, 'skills/gui-automation/src')

# Patch launch_chromium_with_cdp to force headless
from cdp_helper import launch_chromium_with_cdp as original_launch, _is_port_listening, DEFAULT_USER_DATA_DIR
import subprocess

def launch_headless_only(port=9222, url="about:blank"):
    """Modified launcher that tries headless candidates first."""
    os.makedirs(DEFAULT_USER_DATA_DIR, exist_ok=True)

    base_args = [
        f'--remote-debugging-port={port}',
        '--remote-allow-origins=*',
        '--no-first-run',
        '--no-default-browser-check',
        f'--user-data-dir={DEFAULT_USER_DATA_DIR}',
        url
    ]

    # Headless-only candidates, in order of preference
    candidates = [
        ['chromium-browser', '--headless=new'] + base_args,
        ['chromium', '--headless=new'] + base_args,
        ['snap', 'run', 'chromium', '--headless=new'] + base_args,
        # Fallback: non-headless (will likely fail without X)
        ['chromium-browser'] + base_args,
        ['snap', 'run', 'chromium'] + base_args,
    ]

    for cmd in candidates:
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(3)
            if _is_port_listening(port):
                return proc
            time.sleep(2)
            if _is_port_listening(port):
                return proc
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except:
                pass
        except FileNotFoundError:
            continue
        except Exception:
            continue
    return None

def random_username():
    import random, string
    return "testuser_" + ''.join(random.choices(string.digits, k=8))

def click_next_button(cdp):
    """Coordinate-based click for Next button."""
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
        print(f"  Clicking Next at ({x},{y}) text: '{res.get('text')}'")
        cdp.dispatch_mouse(x, y)
        return True
    print("  Next button not found")
    return False

def main():
    print("=== Google Signup (Headless-Only Test) ===")

    # Launch
    proc = launch_headless_only()
    if not proc:
        print("❌ Failed to launch headless Chromium")
        return

    print(f"✅ Launched Chromium headless (PID={proc.pid})")

    client = CDPClient()
    if not client.is_available():
        print("❌ CDP not available")
        proc.terminate()
        return

    print("✅ CDP available")

    # Navigate
    print("Navigating to Google signup...")
    if not client.navigate("https://accounts.google.com/signup"):
        print("❌ Navigation failed")
        proc.terminate()
        return
    time.sleep(4)

    # Fill name
    print("Filling firstName and lastName...")
    if not client.type_in_element("input[name='firstName']", "Test"):
        print("❌ Could not fill firstName")
    if not client.type_in_element("input[name='lastName']", "User"):
        print("❌ Could not fill lastName")

    time.sleep(1)
    print("Clicking Next...")
    if click_next_button(client):
        print("✅ Next clicked")
        time.sleep(3)

        # Screenshot
        b64 = client.take_screenshot()
        if b64:
            os.makedirs("screenshots/google_demo", exist_ok=True)
            path = "screenshots/google_demo/step_headless_test.png"
            with open(path, "wb") as f:
                f.write(b64)
            print(f"✅ Screenshot saved: {path}")
        else:
            print("❌ Screenshot failed")

        print("✅ Test passed: filled name and clicked Next")
    else:
        print("❌ Could not find/click Next button")
        # Debug: dump page info
        title = client.get_page_title()
        url = client.get_page_url()
        print(f"Page title: {title}")
        print(f"Page URL: {url}")

    proc.terminate()
    try:
        proc.wait(timeout=3)
    except:
        pass
    print("✅ Chromium terminated")

if __name__ == "__main__":
    main()
