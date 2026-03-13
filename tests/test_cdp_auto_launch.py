#!/usr/bin/env python3
"""Test that CDP tools auto-launch Chromium when not running."""

import sys
import os
import time
import subprocess

# Ensure we use the workspace version
sys.path.insert(0, '/home/hung/.openclaw/workspace/ClawUI/skills/gui-automation')

from src.agent import _get_cdp

def kill_existing_chromium():
    """Kill any running Chromium with remote debugging to start fresh."""
    subprocess.run(['pkill', '-f', 'chromium.*remote-debugging'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)

def main():
    print("=== CDP Auto-Launch Test ===")
    kill_existing_chromium()
    print("No Chromium running. Getting CDP client (should auto-launch)...")

    start = time.time()
    cdp = _get_cdp()
    elapsed = time.time() - start

    if cdp and cdp.is_available():
        print(f"✅ CDP client obtained in {elapsed:.2f}s")
        print(f"   Browser reachable at {cdp.host}:{cdp.port}")
        # Try a simple operation: list targets
        print("   Testing CDP: listing browser targets...")
        targets = cdp.list_targets()
        pages = [t for t in targets if t.get("type") == "page"]
        print(f"   Found {len(pages)} page(s)")
        if len(pages) >= 1:
            print("✅ CDP operational")
            result = 0
        else:
            print("❌ No page targets found")
            result = 1
        # Clean up: close browser
        try:
            active = cdp.get_active_tab()
            if active:
                cdp.close_target(active.get("id"))
        except:
            pass
        return result
    else:
        print("❌ Failed to get CDP client (auto-launch may have failed)")
        return 1

if __name__ == "__main__":
    sys.exit(main())
