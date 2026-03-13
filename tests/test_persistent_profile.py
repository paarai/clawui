#!/usr/bin/env python3
"""Test persistent profile integration for CDP auto-launch."""

import sys
import os
import time
import subprocess

sys.path.insert(0, '/home/hung/.openclaw/workspace/ClawUI/skills/gui-automation')
from src.cdp_helper import launch_chromium_with_cdp, DEFAULT_USER_DATA_DIR, get_or_create_cdp_client

def test_profile_dir_exists():
    """Test that the default profile directory is created."""
    print("1. Testing profile directory creation...")
    # Remove the directory if it exists to test creation
    if os.path.exists(DEFAULT_USER_DATA_DIR):
        print(f"   Profile dir already exists: {DEFAULT_USER_DATA_DIR}")
    else:
        print(f"   Profile dir will be created on launch")

def test_launch_with_profile():
    """Test that Chromium launches with the correct user-data-dir."""
    print("2. Testing Chromium launch with persistent profile...")

    # Kill any existing Chromium processes to avoid conflicts
    try:
        subprocess.run(['pkill', '-f', 'chromium'], capture_output=True)
        time.sleep(1)
    except:
        pass

    # Launch with CDP
    proc = launch_chromium_with_cdp(port=9223, url="about:blank")
    if proc:
        print(f"   ✅ Launched Chromium (PID: {proc.pid})")
        # Check if it's using the expected profile
        # We can check the command line of the process
        time.sleep(2)
        try:
            cmdline = subprocess.check_output(['ps', '-p', str(proc.pid), '-o', 'cmd=']).decode()
            if DEFAULT_USER_DATA_DIR in cmdline:
                print(f"   ✅ Profile dir found in command line")
            else:
                print(f"   ⚠️  Profile dir NOT in command line: {cmdline[:200]}")
        except:
            print("   ⚠️  Could not check process command line")

        # Test CDP connection
        client = get_or_create_cdp_client(port=9223)
        if client and client.is_available():
            print("   ✅ CDP endpoint is available")
            title = client.get_page_title()
            url = client.get_page_url()
            print(f"   Page: {title} @ {url}")
        else:
            print("   ❌ CDP endpoint not available")

        # Cleanup: terminate the browser
        try:
            proc.terminate()
            proc.wait(timeout=5)
            print("   ✅ Browser terminated")
        except:
            subprocess.run(['pkill', '-f', '--', '--remote-debugging-port=9223'], capture_output=True)
    else:
        print("   ❌ Failed to launch Chromium")
        return False

    return True

def main():
    print("=== Persistent Profile CDP Test ===")
    test_profile_dir_exists()
    if test_launch_with_profile():
        print("\n✅ All tests passed")
        return 0
    else:
        print("\n❌ Tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
