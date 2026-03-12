#!/usr/bin/env python3
"""
Interactive template learner for GUI automation.
Records relative positions of UI elements within a window.
Usage: python3 learn_template.py <app_name>
"""

import sys
import os
import json
import time

sys.path.insert(0, 'ClawUI/skills/gui-automation')
from src.agent import execute_tool
from src.x11_helper import list_windows, X11Window

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def find_target_window(app_name_part):
    """Find the target window by partial title match."""
    windows = list_windows()
    for w in windows:
        if app_name_part.lower() in w.title.lower():
            return w
    return None

def learn_element(element_name, win):
    """Prompt user to click the element and record its position relative to window."""
    print(f"\n=== Learning element: '{element_name}' ===")
    print(f"Window: {win.title} ({win.width}x{win.height} at {win.x},{win.y})")
    print("Please click the element using your mouse now...")
    print("(You have 5 seconds to click)")
    
    # Wait for click using xdotool
    import subprocess
    try:
        # Get click coordinates from user
        result = subprocess.run(['xdotool', 'getmouselocation', '--shell'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            mx = int([l for l in lines if l.startswith('X=')][0].split('=')[1])
            my = int([l for l in lines if l.startswith('Y=')][0].split('=')[1])
            # Calculate relative position
            rel_x = (mx - win.x) / win.width
            rel_y = (my - win.y) / win.height
            print(f"  Recorded: window-relative ({rel_x:.3f}, {rel_y:.3f})")
            return {"x": rel_x, "y": rel_y}
        else:
            print("  Error getting mouse location")
            return None
    except Exception as e:
        print(f"  Error: {e}")
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 learn_template.py <app_name_part>")
        print("Example: python3 learn_template.py wechat")
        sys.exit(1)
    
    app_name = sys.argv[1]
    print(f"=== Template Learner for '{app_name}' ===")
    
    # Ensure DISPLAY is set
    if 'DISPLAY' not in os.environ:
        os.environ['DISPLAY'] = ':0'
    
    # Find the window
    print("Looking for window...")
    win = find_target_window(app_name)
    if not win:
        print(f"❌ No window found containing '{app_name}'")
        print("Make sure the application is running and visible.")
        sys.exit(1)
    
    print(f"✅ Found: {win.title}")
    elements = {}
    
    # Interactive learning loop
    while True:
        name = input("\nEnter element name (or press Enter to finish): ").strip()
        if not name:
            break
        pos = learn_element(name, win)
        if pos:
            elements[name] = pos
            print(f"  ✅ Added '{name}': {pos}")
        else:
            print("  ❌ Failed to record")
    
    # Save template
    if not elements:
        print("No elements recorded. Exiting.")
        sys.exit(0)
    
    template = {
        "app_name": app_name,
        "window_title": win.title,
        "window_width": win.width,
        "window_height": win.height,
        "elements": elements,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    out_dir = "templates"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{app_name}.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(template, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Template saved to: {out_path}")
    print("You can now use click_template tool with this app.")

if __name__ == "__main__":
    main()
