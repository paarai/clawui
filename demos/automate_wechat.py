#!/usr/bin/env python3
"""
Automate WeChat DevTools to create and test a mini-game.
Requires: WeChat DevTools installed (snap or wine).
Usage: python3 automate_wechat.py
"""

import os
import sys
import time
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ClawUI/skills/gui-automation'))

from src.agent import execute_tool
from src.perception import find_elements, get_ui_tree_summary
from src.actions import click, type_text, press_key

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def wait_for_window(name_part, timeout=60):
    """Wait for a window containing name_part to appear."""
    log(f"Waiting for window containing: '{name_part}' (timeout {timeout}s)...")
    start = time.time()
    while time.time() - start < timeout:
        apps = find_elements(name=name_part)
        if apps:
            log(f"✅ Found: {apps[0]}")
            return apps[0]
        # Also list what we see for debugging
        if int(time.time() - start) % 10 == 0:
            all_apps = find_elements()
            log(f"  ... waiting, seen {len(all_apps)} apps so far")
        time.sleep(1)
    log(f"❌ Timeout waiting for: {name_part}")
    return None

def main():
    log("=== WeChat DevTools Automation ===")

    # Step 1: Launch WeChat DevTools (snap version)
    log("Launching WeChat DevTools...")
    result = execute_tool("launch_wechat_devtools", {"use_wine": False})
    log(result.get("text", ""))

    # Step 2: Wait for main window
    main_win = wait_for_window("微信开发者工具", timeout=20)
    if not main_win:
        log("Cannot find WeChat DevTools window. Make sure it's installed and can start manually first.")
        return 1

    # Step 3: Take screenshot to see initial state
    screenshot = execute_tool("screenshot", {})
    if screenshot.get("type") == "image":
        log("✅ Screenshot captured (base64)")
    else:
        log("⚠️ Screenshot not available")

    # Step 4: Navigate to "New Project" or similar
    # WeChat DevTools UI is in Chinese. Look for buttons.
    log("Looking for '新建项目' (New Project) button...")
    new_btn = find_elements(name="新建项目") or find_elements(name="New Project")
    if new_btn:
        x, y = new_btn[0].center
        click(x, y)
        log(f"Clicked New Project at ({x}, {y})")
        time.sleep(2)
    else:
        log("Could not find New Project button. Attempting fallback: Alt+N")
        press_key("alt+n")
        time.sleep(2)

    # Step 5: Fill project details
    log("Filling project info...")
    # Project name
    type_text("TestMiniGame")
    press_key("tab")
    time.sleep(0.5)

    # Project directory - just use default, skip
    press_key("tab")
    time.sleep(0.5)

    # AppID - use test appid
    type_text("touristappid")
    time.sleep(0.5)

    # Confirm creation
    press_key("enter")
    log("Project creation initiated...")
    time.sleep(5)

    # Step 6: Editor should open. Replace game code with simple mini-game.
    log("Writing mini-game code...")
    # Clear current file (Ctrl+A then Delete)
    press_key("ctrl+a")
    time.sleep(0.5)
    press_key("delete")
    time.sleep(0.5)

    # Simple mini-game code (catch the apple)
    game_code = '''// 这是一个简单的小游戏：接苹果
// 使用微信小游戏框架
App({
  onLaunch() {
    console.log("Game Launched")
  },
  globalData: {
    score: 0
  }
})

const canvas = wx.createCanvas()
const ctx = canvas.getContext('2d')
canvas.width = 375
canvas.height = 667

let score = 0
let baskets = [{x: 187, y: 550, w: 60, h: 30}]
let apples = []
let nextApple = 0

function draw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.fillStyle = "#87CEEB"
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  // basket
  ctx.fillStyle = "#8B4513"
  baskets.forEach(b => ctx.fillRect(b.x - b.w/2, b.y, b.w, b.h))

  // apples
  ctx.fillStyle = "#FF4500"
  apples.forEach(a => {
    ctx.beginPath()
    ctx.arc(a.x, a.y, 15, 0, Math.PI*2)
    ctx.fill()
  })

  // score
  ctx.fillStyle = "black"
  ctx.font = "20px Arial"
  ctx.fillText("Score: " + score, 10, 30)
}

function update() {
  // spawn apple
  if (Date.now() - nextApple > 1500) {
    apples.push({
      x: Math.random() * canvas.width,
      y: -20,
      speed: 2 + Math.random() * 2
    })
    nextApple = Date.now()
  }

  // update apples
  for (let i = apples.length - 1; i >= 0; i--) {
    apples[i].y += apples[i].speed
    if (apples[i].y > canvas.height) {
      apples.splice(i, 1)
      continue
    }
    // collision with basket
    const b = baskets[0]
    if (apples[i].y + 15 >= b.y &&
        apples[i].x >= b.x - b.w/2 &&
        apples[i].x <= b.x + b.w/2) {
      score++
      apples.splice(i, 1)
    }
  }

  draw()
  requestAnimationFrame(update)
}

// Touch/mouse control
canvas.addEventListener('touchstart', e => {
  const touch = e.touches[0]
  baskets[0].x = touch.clientX
})
canvas.addEventListener('mousedown', e => {
  baskets[0].x = e.clientX
})

update()
'''

    # Type the code (may be slow, just paste as chunk)
    type_text(game_code)
    time.sleep(2)

    # Save file
    press_key("ctrl+s")
    log("Game code saved.")
    time.sleep(1)

    # Step 7: Compile/Run (assuming auto-preview)
    log("Requesting preview...")
    press_key("ctrl+r")
    time.sleep(3)

    # Step 8: Final screenshot
    screenshot = execute_tool("screenshot", {})
    if screenshot.get("type") == "image":
        log("✅ Final screenshot captured")
    else:
        log("⚠️ Could not capture final screenshot")

    log("=== Automation completed ===")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
