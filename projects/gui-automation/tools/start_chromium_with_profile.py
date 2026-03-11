#!/usr/bin/env python3
"""
Start Chromium with your existing user profile for CDP automation.
This reuses your daily browser session (with logins, cookies, etc.).
"""

import subprocess
import os
import time
import sys

def detect_profile():
    """Try to locate Chromium/Chrome user data directory."""
    # Snap Chromium (Ubuntu/Debian)
    snap_path = os.path.expanduser("~/snap/chromium/common/chromium/")
    if os.path.exists(snap_path):
        return snap_path
    # Native Chromium
    native_path = os.path.expanduser("~/.config/chromium/")
    if os.path.exists(native_path):
        return native_path
    # Google Chrome
    chrome_path = os.path.expanduser("~/.config/google-chrome/")
    if os.path.exists(chrome_path):
        return chrome_path
    return None

def main():
    profile = detect_profile()
    if not profile:
        print("ERROR: Could not find Chromium/Chrome profile directory.")
        print("Install Chromium or set profile manually.")
        sys.exit(1)

    print(f"Using profile: {profile}")

    # Stop any existing Chromium with CDP
    subprocess.run(["pkill", "-f", "chromium.*remote-debugging"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Start Chromium with CDP and reuse existing profile
    # WARNING: This may open a new window; use --remote-debugging-port only, avoid --new-window if you want to reuse existing instance (but remote debugging requires fresh start usually).
    cmd = [
        "snap", "run", "chromium",
        f"--user-data-dir={profile}",
        "--remote-debugging-port=9222",
        "--remote-allow-origins=*",
        "--no-first-run"
    ]
    print("Starting Chromium:", " ".join(cmd))
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Wait for CDP
    import urllib.request
    import json
    for i in range(15):
        try:
            with urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=1) as resp:
                data = json.load(resp)
                print(f"Chromium ready: {data['Browser']}")
                return
        except:
            time.sleep(1)
    print("WARNING: CDP did not respond in time. Chromium may have failed to start.")

if __name__ == "__main__":
    main()
