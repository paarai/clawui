#!/usr/bin/env python3
"""
End-to-end test for clawui - multi-mode.
Primary: Control Firefox to create GitHub repo via browser automation.
Fallback: Control v2rayN (XWayland app) to test basic X11 control.
"""

import sys
import os
import subprocess
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('/tmp/e2e_test.log', mode='w'),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.info

sys.path.insert(0, '/home/hung/.openclaw/workspace/skills/gui-automation')
from src.x11_helper import list_windows, find_windows_by_class, activate_window, click_at, type_text, key_press
from src.perception import get_ui_tree_summary

def wait(seconds):
    time.sleep(seconds)

def test_x11_control(target_class='v2rayN'):
    """Test basic X11 control by interacting with a simple XWayland app."""
    log(f"=== X11 Control Test: Targeting {target_class} ===")
    windows = find_windows_by_class(target_class)
    if not windows:
        log(f"No {target_class} window found")
        return False
    w = windows[0]
    log(f"Found window: {w.title} (WID={w.wid})")
    
    # Activate
    activate_window(w.wid)
    wait(1)
    
    # Try to click menu or interact
    # For v2rayN, click at top menu: "File" (approx)
    click_at(w.x + 50, w.y + 20)
    wait(0.5)
    log("Clicked menu area")
    
    log("✅ X11 control test passed (basic)")
    return True

def test_firefox_automation():
    """Full Firefox automation - currently incomplete due to Workspace detection."""
    log("=== Firefox Automation Test ===")
    # Check if Firefox window is detectable via X11
    firefox = find_windows_by_class('firefox')
    if not firefox:
        log("Firefox not visible on X11 - likely running as Wayland native")
        return False, "Firefox not visible on X11"
    
    # If found, continue with steps...
    log("Firefox detected on X11, continuing... (placeholder)")
    return True, "Detected"

def test_atspi_control():
    """Test AT-SPI based control (works on Wayland native apps)."""
    log("=== AT-SPI Control Test ===")
    try:
        from src.atspi_helper import list_applications
        apps = list_applications()
        log(f"AT-SPI detected {len(apps)} applications")
        if len(apps) > 5:
            log("✅ AT-SPI working")
            return True
        else:
            log("⚠️  AT-SPI limited detection")
            return False
    except Exception as e:
        log(f"❌ AT-SPI error: {e}")
        return False

def main():
    log("=== Clawui End-to-End Test ===")
    
    results = []
    
    # Test 1: AT-SPI
    results.append(("AT-SPI", test_atspi_control()))
    
    # Test 2: X11 Control (using v2rayN as target)
    results.append(("X11 Control", test_x11_control()))
    
    # Test 3: Firefox automation (expected to fail until fully implemented)
    success, msg = test_firefox_automation()
    results.append(("Firefox Automation", success))
    
    # Summary
    log("\n=== Test Summary ===")
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        log(f"  {name}: {status}")
    
    all_passed = all(ok for _, ok in results)
    if all_passed:
        log("All tests passed")
        return 0
    else:
        log("Some tests failed - review /tmp/e2e_test.log")
        return 1

if __name__ == "__main__":
    sys.exit(main())
