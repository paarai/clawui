#!/usr/bin/env python3
"""
Detect and control WeChat DevTools using ClawUI.
Handles Chinese/English naming variations.
"""

import sys
import os
import subprocess
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ClawUI/skills/gui-automation'))

from src.perception import list_applications, find_elements, get_ui_tree_summary
from src.x11_helper import list_windows, find_windows_by_title, activate_window, click_at
from src.actions import type_text, press_key

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

# Common names for WeChat DevTools (Chinese/English variations)
WECHAT_DEVTOOL_NAMES = [
    "微信开发者工具",
    "WeChat DevTools",
    "WeChat Developer Tools",
    "微信开发者工具 - 未命名",
    "WeChat DevTools - index",
    "微信Web开发者工具",
]

def find_wechat_devtools():
    """Try to find WeChat DevTools window."""
    windows = list_windows()
    for win in windows:
        title_lower = win.title.lower()
        if any(name.lower() in title_lower for name in WECHAT_DEVTOOL_NAMES):
            return win
    return None

def start_wechat_devtools():
    """Attempt to start WeChat DevTools from common locations."""
    possible_paths = [
        os.path.expanduser("~/Applications/微信开发者tools/微信开发者工具"),
        os.path.expanduser("~/Applications/WeChatDevTools/WeChatDevTools"),
        "/usr/share/applications/wechat-dev-tools.desktop",
        "/opt/wechat-dev-tools/wechat-dev-tools",
        os.path.expanduser("~/.local/share/applications/wechat-dev-tools.desktop"),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            log(f"Found at: {path}")
            try:
                subprocess.Popen([path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                log("Launched WeChat DevTools")
                return True
            except Exception as e:
                log(f"Launch failed: {e}")
    return False

def main():
    log("=== WeChat DevTools Detection ===")

    # List current apps
    apps = list_applications()
    log(f"Running apps: {len(apps)}")

    # Check if already running
    win = find_wechat_devtools()
    if win:
        log(f"✅ Found WeChat DevTools window: {win.title}")
        log(f"   Window ID: {win.wid}")
        activate_window(win)
        log("Activated window")
    else:
        log("WeChat DevTools not currently running")
        if start_wechat_devtools():
            log("Waiting for window to appear...")
            for _ in range(10):
                time.sleep(1)
                win = find_wechat_devtools()
                if win:
                    log(f"✅ Started and found: {win.title}")
                    activate_window(win)
                    break
            else:
                log("❌ Window still not found after launch attempt")
        else:
            log("❌ Could not find executable to launch")
            log("Please install WeChat DevTools or ensure it's in PATH")

    # Show UI tree around the window if found
    if win:
        log("\n=== UI Tree Preview (first 30 lines) ===")
        tree = get_ui_tree_summary(app_name="wechat", max_depth=4) or get_ui_tree_summary(max_depth=4)
        lines = tree.split('\n')[:30]
        print("\n".join(lines))

if __name__ == "__main__":
    main()
