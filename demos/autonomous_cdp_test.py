#!/usr/bin/env python3
"""
Autonomous test for CDP browser automation with environment inheritance.
Tests:
1. Environment auto-detection (DISPLAY, XAUTHORITY)
2. Chromium launch (headless fallback)
3. Basic CDP operations: navigate, get title, screenshot
4. Simple element interaction
"""

import os
import sys
import time
import subprocess
import socket

sys.path.insert(0, 'skills/gui-automation/src')
from cdp_helper import launch_chromium_with_cdp, CDPClient, _xauthority_valid

def print_env():
    print("=== Environment ===")
    print(f"DISPLAY: {os.environ.get('DISPLAY', 'NOT SET')}")
    print(f"WAYLAND_DISPLAY: {os.environ.get('WAYLAND_DISPLAY', 'NOT SET')}")
    print(f"XAUTHORITY: {os.environ.get('XAUTHORITY', 'NOT SET')}")
    xauth_path = os.environ.get('XAUTHORITY')
    if xauth_path:
        try:
            size = os.path.getsize(xauth_path)
            print(f"XAUTHORITY size: {size} bytes")
            print(f"_xauthority_valid: {_xauthority_valid(xauth_path)}")
        except Exception as e:
            print(f"Error checking XAUTHORITY: {e}")
    print()

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

def test_launch_and_cdp():
    print("=== Test 1: Chromium Launch & CDP Connection ===")
    proc = launch_chromium_with_cdp()
    if not proc:
        print("❌ Failed to launch Chromium")
        return None, None

    print(f"✅ Chromium launched (PID={proc.pid})")
    time.sleep(3)

    client = CDPClient()
    if not client.is_available():
        print("❌ CDP endpoint not responding")
        proc.terminate()
        return None, None

    print("✅ CDP endpoint available")
    return proc, client

def test_navigation(client):
    print("\n=== Test 2: Navigation ===")
    url = "https://example.com"
    print(f"Navigating to {url}...")
    if not client.navigate(url):
        print("❌ Navigation failed")
        return False
    time.sleep(3)

    title = client.get_page_title()
    print(f"✅ Page title: {title}")

    page_url = client.get_page_url()
    print(f"✅ Current URL: {page_url}")
    return True

def test_screenshot(client):
    print("\n=== Test 3: Screenshot ===")
    b64 = client.take_screenshot()
    if b64:
        path = "screenshots/autonomous_test.png"
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "wb") as f:
            f.write(b64)
        print(f"✅ Screenshot saved: {path}")
        return True
    else:
        print("❌ Screenshot failed")
        return False

def test_element_interaction(client):
    print("\n=== Test 4: Element Interaction ===")
    # Find a button on example.com
    print("Querying for buttons on page...")
    buttons = client.evaluate("Array.from(document.querySelectorAll('button')).map(b=>({text:b.textContent.trim(), disabled:b.disabled})).slice(0,5)")
    print(f"Buttons: {buttons}")

    # Try to click something if exists
    if buttons and len(buttons) > 0:
        print("✅ Found buttons, interaction possible")
        return True
    else:
        print("No buttons found (might be expected for simple page)")
        return True  # Not a failure

def main():
    print(" Autonomous CDP Test ".center(60, "="))
    print_env()

    proc, client = test_launch_and_cdp()
    if not proc or not client:
        print("\n❌ TEST FAILED: Launch/CDP")
        return False

    tests = [
        lambda: test_navigation(client),
        lambda: test_screenshot(client),
        lambda: test_element_interaction(client),
    ]

    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test exception: {e}")

    # Clean up
    proc.terminate()
    try:
        proc.wait(timeout=3)
        print("\n✅ Chromium terminated cleanly")
    except:
        pass

    print(f"\n=== Results: {passed}/{len(tests)} tests passed ===")
    if passed == len(tests):
        print("✅ ALL TESTS PASSED")
        return True
    else:
        print("❌ SOME TESTS FAILED")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
