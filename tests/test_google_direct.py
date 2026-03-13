#!/usr/bin/env python3
"""
Direct test: manually start headless Chromium, then connect and test Google signup flow.
"""

import sys, os, time, subprocess, socket, json

sys.path.insert(0, 'skills/gui-automation/src')
from cdp_helper import CDPClient

def wait_for_port(port, timeout=10):
    for _ in range(timeout):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            if result == 0:
                return True
        except:
            pass
        time.sleep(1)
    return False

def main():
    port = 9228
    profile_dir = '/tmp/google_test_' + str(int(time.time()))

    # Start Chromium headless
    cmd = [
        '/snap/bin/chromium',
        '--headless=new',
        f'--remote-debugging-port={port}',
        '--remote-allow-origins=*',
        '--no-first-run',
        '--no-default-browser-check',
        f'--user-data-dir={profile_dir}',
        'about:blank'
    ]
    print("Starting:", ' '.join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Process PID: {proc.pid}")

    if wait_for_port(port):
        print(f"✅ Port {port} is listening")
    else:
        print("❌ Port not listening, killing browser")
        proc.terminate()
        return

    # Connect via CDP
    client = CDPClient(port=port)
    time.sleep(1)

    if not client.is_available():
        print("❌ CDP not available")
        proc.terminate()
        return

    print("✅ CDP connected")

    # Navigate to Google signup
    print("Navigating to https://accounts.google.com/signup ...")
    if not client.navigate("https://accounts.google.com/signup"):
        print("❌ Navigation failed")
        proc.terminate()
        return

    time.sleep(4)
    title = client.get_page_title()
    print(f"Page title: {title}")

    # Fill firstName and lastName
    print("Filling first name 'Test'...")
    client.type_in_element("input[name='firstName']", "Test")
    print("Filling last name 'User'...")
    client.type_in_element("input[name='lastName']", "User")

    time.sleep(1)

    # Find and click Next using JS
    print("Finding Next button...")
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
    res = client.evaluate(find_script)
    if res and 'x' in res:
        x, y = int(res['x']), int(res['y'])
        print(f"Found Next: '{res.get('text')}' at ({x},{y})")
        print("Clicking via dispatch_mouse...")
        client.dispatch_mouse(x, y)
        print("✅ Click dispatched")
    else:
        print("❌ Next button not found")
        print("Dumping some info:")
        btns = client.evaluate("Array.from(document.querySelectorAll('button')).map(b=>b.textContent.trim()).slice(0,5)")
        print("Buttons:", btns)

    time.sleep(3)

    # Screenshot
    b64 = client.take_screenshot()
    if b64:
        os.makedirs('screenshots/google_demo', exist_ok=True)
        path = 'screenshots/google_demo/step_headless_final.png'
        with open(path, 'wb') as f:
            f.write(b64)
        print(f"✅ Screenshot saved: {path}")
    else:
        print("❌ Screenshot failed")

    # Clean up
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except:
        pass
    print("✅ Done")

if __name__ == "__main__":
    main()
