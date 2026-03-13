#!/usr/bin/env python3
"""Test CDP auto-launch reliability."""
import sys
import os

print("=== Initial environment ===")
print("DISPLAY:", os.environ.get('DISPLAY'))
print("XAUTHORITY:", os.environ.get('XAUTHORITY'))
print("WAYLAND_DISPLAY:", os.environ.get('WAYLAND_DISPLAY'))

# Insert path and import (this runs ensure_gui_environment())
sys.path.insert(0, '/home/hung/.openclaw/workspace/skills/gui-automation/src')
from cdp_helper import launch_chromium_with_cdp, get_or_create_cdp_client

print("\n=== After import ===")
print("DISPLAY:", os.environ.get('DISPLAY'))
print("XAUTHORITY:", os.environ.get('XAUTHORITY'))
print("WAYLAND_DISPLAY:", os.environ.get('WAYLAND_DISPLAY'))

print("\n=== Testing get_or_create_cdp_client ===")
client = get_or_create_cdp_client()
if client:
    print("CDP client obtained")
    print("Available:", client.is_available())
    tabs = client.list_targets()
    print("Number of tabs:", len(tabs))
    for t in tabs:
        print(f"  - {t.get('title', '')[:50]} ({t.get('type')})")
else:
    print("Failed to get CDP client")

# Also test direct launch
print("\n=== Testing direct launch ===")
proc = launch_chromium_with_cdp()
if proc:
    print("Launched successfully, PID:", proc.pid)
    # Give it a moment to be ready
    import time; time.sleep(2)
    print("Client available after launch:", client.is_available() if client else 'N/A')
    proc.terminate()
    try:
        proc.wait(timeout=5)
        print("Terminated")
    except:
        proc.kill()
        print("Killed")
else:
    print("Launch FAILED")
