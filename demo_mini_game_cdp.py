#!/usr/bin/env python3
"""
Automate creation of a simple mini-game using CDP (browser-based).
This simulates what would be done in WeChat DevTools if it were available.
Target: Create a "Catch the Dot" game in a code sandbox.
"""

import sys
import os
import time
import base64

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ClawUI/skills/gui-automation'))

from src.perception import get_ui_tree_summary, find_elements
from src.agent import execute_tool
from src.screenshot import take_screenshot

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def take_and_save(name):
    b64 = take_screenshot()
    if b64:
        path = f"screenshots/demo_{name}_{int(time.time())}.png"
        os.makedirs("screenshots", exist_ok=True)
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64))
        log(f"Screenshot saved: {path}")
        return path
    return None

def main():
    log("=== 浏览器小游戏自动创建演示 ===")

    # Step 1: Check CDP availability
    log("Checking CDP availability...")
    cdp_info = execute_tool("cdp_page_info", {})
    log(f"CDP status: {cdp_info.get('text', 'no info')}")

    # Step 2: Navigate to a code sandbox (e.g., CodePen or JSFiddle)
    log("Navigating to CodePen...")
    result = execute_tool("cdp_navigate", {"url": "https://codepen.io/pen/define"})
    log(result.get("text", ""))

    time.sleep(3)
    take_and_save("codepen_landed")

    # Step 3: Check page content
    log("Getting page info...")
    info = execute_tool("cdp_page_info", {})
    log(f"Page: {info.get('text', '')}")

    # Step 4: Fill in HTML content (simple canvas game)
    html_code = '''<!DOCTYPE html>
<html>
<head>
  <title> Catch the Dot </title>
  <style>
    body { margin: 0; overflow: hidden; background: #111; }
    canvas { display: block; }
    #score { position: absolute; top: 10px; left: 10px; color: white; font-family: sans-serif; font-size: 24px; }
  </style>
</head>
<body>
  <div id="score">0</div>
  <canvas id="game"></canvas>
  <script>
    const canvas = document.getElementById('game');
    const ctx = canvas.getContext('2d');
    const scoreEl = document.getElementById('score');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    let score = 0;
    let dot = { x: canvas.width/2, y: canvas.height/2, r: 20, color: '#ff0' };
    let speed = 2;

    function draw() {
      ctx.fillStyle = '#111';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = dot.color;
      ctx.beginPath();
      ctx.arc(dot.x, dot.y, dot.r, 0, Math.PI*2);
      ctx.fill();
    }

    function update() {
      dot.x += (Math.random() - 0.5) * speed * 10;
      dot.y += (Math.random() - 0.5) * speed * 10;
      dot.x = Math.max(dot.r, Math.min(canvas.width - dot.r, dot.x));
      dot.y = Math.max(dot.r, Math.min(canvas.height - dot.r, dot.y));
      draw();
    }

    canvas.addEventListener('click', (e) => {
      const dx = e.clientX - dot.x;
      const dy = e.clientY - dot.y;
      if (Math.sqrt(dx*dx + dy*dy) < dot.r) {
        score++;
        scoreEl.textContent = score;
        dot.x = Math.random() * canvas.width;
        dot.y = Math.random() * canvas.height;
        dot.r = 15 + Math.random() * 15;
        dot.color = `hsl(${Math.random()*360}, 80%, 60%)`;
      }
    });

    setInterval(update, 1000/60);
    draw();
  </script>
</body>
</html>'''

    log("Injecting HTML code via JavaScript...")
    # This is tricky on a form; let's use cdp_eval to set innerHTML of editor if possible
    # But CodePen uses a complex editor. Instead, we'll navigate to a direct data URL.
    data_url = "data:text/html;charset=utf-8," + base64.b64encode(html_code.encode()).decode()
    log(f"Navigating to data URL with game...")
    result = execute_tool("cdp_navigate", {"url": data_url})
    log(result.get("text", ""))

    time.sleep(3)
    take_and_save("game_loaded")

    # Step 5: Verify the game runs by taking a screenshot (canvas should show)
    log("Game should now be running. Taking screenshot to verify...")
    screenshot_result = execute_tool("cdp_screenshot", {})
    if screenshot_result.get("type") == "image":
        take_and_save("game_running")
        log("✅ Screenshot captured - game appears loaded")
    else:
        log("❌ Screenshot failed")

    # Step 6: Simple interaction test - try to programmatically simulate a click
    log("Testing programmatic click on canvas to score a point...")
    click_js = "const canvas = document.querySelector('canvas'); if(canvas){ canvas.click(); true } else { false }"
    result = execute_tool("cdp_eval", {"expression": click_js})
    log(f"Simulated click: {result.get('text', '')}")

    time.sleep(1)
    take_and_save("after_click")

    log("=== Demo completed ===")
    log("Note: If WeChat DevTools were available, similar CDP-based flow would work for its built-in browser preview.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
