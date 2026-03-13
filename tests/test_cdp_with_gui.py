#!/usr/bin/env python3
"""
Direct test: launch Chromium, navigate, and click using CDP.
"""

import os
import sys
import time

# Ensure we can import from skills
sys.path.insert(0, 'skills/gui-automation/src')

# Import and let it set up environment
from cdp_helper import launch_chromium_with_cdp, CDPClient

def main():
    print('=== CDP Browser Automation Test ===')
    print('Environment:')
    print(f'  DISPLAY={os.environ.get("DISPLAY", "NOT SET")}')
    print(f'  WAYLAND_DISPLAY={os.environ.get("WAYLAND_DISPLAY", "NOT SET")}')
    print(f'  XAUTHORITY={os.environ.get("XAUTHORITY", "NOT SET")}')
    print()

    print('Launching Chromium...')
    proc = launch_chromium_with_cdp()
    if not proc:
        print('❌ Failed to launch Chromium')
        return

    print(f'✅ Chromium launched (PID={proc.pid})')
    time.sleep(3)

    client = CDPClient()
    if not client.is_available():
        print('❌ CDP not available')
        proc.terminate()
        return

    print('✅ CDP endpoint available')

    # List targets
    targets = client.list_targets()
    print(f'Found {len(targets)} targets')
    for t in targets:
        url = t.get('url', 'about:blank')
        print(f"  - {t.get('type')}: {url}")

    # Navigate to a test page
    print('\\nNavigating to https://example.com...')
    if client.navigate('https://example.com'):
        print('✅ Navigation command sent')
    else:
        print('❌ Navigation failed')
        proc.terminate()
        return

    time.sleep(3)

    # Get title and screenshot
    title = client.get_page_title()
    print(f'Page title: {title}')

    screenshot_dir = 'screenshots'
    os.makedirs(screenshot_dir, exist_ok=True)
    b64 = client.take_screenshot()
    if b64:
        path = os.path.join(screenshot_dir, 'test_example.png')
        with open(path, 'wb') as f:
            f.write(b64)
        print(f'✅ Screenshot saved: {path}')
    else:
        print('❌ Screenshot failed')

    # Clean up
    proc.terminate()
    try:
        proc.wait(timeout=3)
        print('✅ Chromium terminated')
    except:
        proc.kill()
        print('⚠️ Chromium killed')

    print('\\n=== Test completed ===')

if __name__ == '__main__':
    main()
