#!/usr/bin/env python3
"""
Simple rule-based automation for WeChat DevTools.
This demonstrates the plan_and_execute concept without needing an LLM.
"""

import sys, os, time
sys.path.insert(0, 'ClawUI/skills/gui-automation')
from src.agent import execute_tool

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def run_task(task: str):
    log(f"Task: {task}")
    
    # Simple task parser
    if "微信开发者工具" in task and ("创建" in task or "新建" in task):
        return run_create_project()
    else:
        log("Unsupported task for simple planner")
        return {"error": "no planner"}

def run_create_project():
    steps = [
        ("wait_for_window", {"title_contains": "微信开发者工具", "timeout": 60}),
        ("activate_window", {"title_contains": "微信开发者工具"}),
        ("describe_screen", {"detail": "brief"}),
        # Locate "新建项目" button using vision or fuzzy find
        # Then click, fill, etc.
    ]
    history = []
    for i, (tool, inp) in enumerate(steps, 1):
        log(f"Step {i}: {tool} {inp}")
        try:
            result = execute_tool(tool, inp)
            history.append({"step": i, "tool": tool, "input": inp, "output": result})
            log(f" → {result.get('text','')[:80]}")
        except Exception as e:
            log(f" ERROR: {e}")
            break
        time.sleep(1)
    return {"completed": True, "history": history}

if __name__ == "__main__":
    task = "在微信开发者工具中创建一个小游戏项目"
    result = run_task(task)
    print("\n=== Summary ===")
    print(f"Steps executed: {len(result.get('history',[]))}")
    print("Done.")
