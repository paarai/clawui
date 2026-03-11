#!/usr/bin/env python3
"""Simple adaptive GUI automation without heavy vision model.

Uses AT-SPI tree + simple coordinate heuristics to simulate AI decisions.
"""

import sys, os, time

sys.path.insert(0, '/home/hung/.openclaw/workspace/skills/gui-automation')
from src.atspi_helper import find_elements, do_action
from src.actions import click
from src.screenshot import take_screenshot

def find_and_click(name, role='push button'):
    """Find UI element by name and click."""
    elems = find_elements(role=role, name=name)
    if elems:
        e = elems[0]
        click(e.x + e.width//2, e.y + e.height//2)
        return True
    return False

def adaptive_loop(task):
    print(f"\n🤖 Adaptive Agent: {task}\n")
    
    for step in range(1, 11):
        print(f"--- Step {step} ---")
        # 1. Get UI tree snapshot
        try:
            elems = find_elements(role='push button')
            button_names = [e.name for e in elems[:10]]
            print(f"  Buttons: {button_names}")
            
            # 2. Simple decision based on task
            task_lower = task.lower()
            if 'calculator' in task_lower:
                if not any('calculator' in w.lower() for w in get_active_window_name()):
                    focus_window('计算器') or focus_window('Calculator')
                    time.sleep(0.5)
                    continue
                    
                # Extract numbers and operator
                import re
                m = re.search(r'(\d+)\s*([\+\-\*/×x])\s*(\d+)', task)
                if m:
                    a, op, b = m.groups()
                    seq = list(a + op.replace('×','*').replace('x','*') + b)
                    seq.append('Return')  # =
                    
                    # Find buttons by name
                    for ch in seq:
                        if find_and_click(ch):
                            time.sleep(0.2)
                        else:
                            print(f"  Could not find button '{ch}'")
                            return False
                    return True
            
            print("  Task not understood, waiting...")
            time.sleep(1)
            
        except Exception as e:
            print(f"  Error: {e}")
            time.sleep(1)
    
    return False

def get_active_window_name():
    """Get current active window name."""
    try:
        from src.actions import get_active_window
        win = get_active_window()
        return win.get('name', '')
    except:
        return ''

if __name__ == "__main__":
    task = " ".join(sys.argv[1:]) or "Open calculator and compute 42*13"
    success = adaptive_loop(task)
    print(f"\n{'✅ Success' if success else '❌ Failed'}")
    sys.exit(0 if success else 1)
