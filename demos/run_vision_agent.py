#!/usr/bin/env python3
"""
Adaptive Vision Agent - AI-driven GUI automation loop.

Flow:
1. Take screenshot + get AT-SPI tree
2. Send to vision model (Ollama/OpenAI) with task description
3. Parse JSON action response
4. Execute action (click/type/press/scroll)
5. Verify result (screenshot again)
6. Repeat until task complete or max steps

Usage:
    python3 run_vision_agent.py "Open calculator and compute 42 * 13"
    python3 run_vision_agent.py --model moondream "Click the Files icon"
    python3 run_vision_agent.py --api-base http://localhost:11434/v1 --model llava:7b "task"
"""

import argparse
import base64
import json
import sys
import time
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'skills', 'gui-automation'))

from src.screenshot import take_screenshot, get_screen_size
from src.actions import click, type_text, press_key, scroll, focus_window
from src.atspi_helper import list_applications, get_ui_tree_summary


def resize_screenshot(b64_data: str, max_width: int = 800) -> str:
    """Resize screenshot to reduce size for faster model inference."""
    try:
        from PIL import Image
        import io
        img_bytes = base64.b64decode(b64_data)
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        return base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        return b64_data  # No PIL, return original

SYSTEM_PROMPT = """You are a GUI automation agent controlling a Linux desktop.

You receive:
- A screenshot of the current screen
- A text description of visible UI elements (from AT-SPI accessibility tree)

Your task: analyze the screen and decide the NEXT SINGLE ACTION to take.

Respond with ONLY a JSON object (no markdown, no explanation):

{
  "thinking": "brief analysis of what you see and what to do next",
  "action": "click|type|press|scroll|focus|done|fail",
  "params": {
    // For click: {"x": 123, "y": 456}
    // For type: {"text": "hello world"}
    // For press: {"key": "Return"} or {"key": "ctrl+c"}
    // For scroll: {"direction": "down", "amount": 3}
    // For focus: {"window": "Calculator"}
    // For done: {"result": "description of what was accomplished"}
    // For fail: {"reason": "why the task cannot be completed"}
  }
}

Rules:
- ONE action per response
- Use precise coordinates from the screenshot
- Prefer keyboard shortcuts when efficient
- Say "done" when the task is complete
- Say "fail" if stuck after multiple attempts
"""


def build_message(task: str, screenshot_b64: str, ui_tree: str, step: int, history: list) -> list:
    """Build multi-modal message for vision model."""
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Add history (previous actions and results)
    for h in history[-6:]:  # Keep last 6 exchanges to limit context
        msgs.append(h)

    # Current turn
    content = []
    content.append({
        "type": "text",
        "text": f"Task: {task}\nStep: {step}\n\nUI Elements:\n{ui_tree[:2000]}\n\nWhat is the next action?"
    })
    content.append({
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}
    })
    msgs.append({"role": "user", "content": content})
    return msgs


def call_vision_model(messages: list, api_base: str, model: str, api_key: str = "") -> dict:
    """Call vision model and parse JSON response."""
    import httpx

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 512,
        "stream": False,
    }

    try:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(f"{api_base}/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]

            # Try to parse JSON from response
            # Strip markdown code blocks if present
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
            if text.startswith("json"):
                text = text[4:].strip()

            return json.loads(text)
    except json.JSONDecodeError as e:
        return {"action": "fail", "params": {"reason": f"JSON parse error: {e}\nRaw: {text[:200]}"}}
    except Exception as e:
        return {"action": "fail", "params": {"reason": f"API error: {e}"}}


def execute_action(action: dict) -> str:
    """Execute parsed action and return result description."""
    act = action.get("action", "fail")
    params = action.get("params", {})
    thinking = action.get("thinking", "")

    if thinking:
        print(f"  💭 {thinking}")

    try:
        if act == "click":
            x, y = int(params["x"]), int(params["y"])
            click(x, y)
            return f"Clicked ({x}, {y})"

        elif act == "type":
            text = params["text"]
            type_text(text)
            return f"Typed: {text}"

        elif act == "press":
            key = params["key"]
            press_key(key)
            return f"Pressed: {key}"

        elif act == "scroll":
            direction = params.get("direction", "down")
            amount = int(params.get("amount", 3))
            scroll(direction, amount)
            return f"Scrolled {direction} {amount}"

        elif act == "focus":
            window = params["window"]
            focus_window(window)
            return f"Focused: {window}"

        elif act == "done":
            result = params.get("result", "Task completed")
            return f"DONE: {result}"

        elif act == "fail":
            reason = params.get("reason", "Unknown failure")
            return f"FAIL: {reason}"

        else:
            return f"Unknown action: {act}"

    except Exception as e:
        return f"Error executing {act}: {e}"


def run_agent(task: str, api_base: str, model: str, api_key: str = "",
              max_steps: int = 20, delay: float = 1.0):
    """Run the adaptive vision agent loop."""
    print(f"\n🤖 Vision Agent Starting")
    print(f"   Task: {task}")
    print(f"   Model: {model} @ {api_base}")
    print(f"   Max steps: {max_steps}\n")

    history = []
    screen_w, screen_h = get_screen_size()
    print(f"   Screen: {screen_w}x{screen_h}\n")

    for step in range(1, max_steps + 1):
        print(f"--- Step {step}/{max_steps} ---")

        # 1. Capture state (resize screenshot for faster inference)
        screenshot_raw = take_screenshot()
        screenshot = resize_screenshot(screenshot_raw, max_width=800)
        try:
            ui_tree = get_ui_tree_summary(max_depth=2)
        except:
            ui_tree = "(AT-SPI unavailable)"

        # 2. Build prompt and call model
        messages = build_message(task, screenshot, ui_tree, step, history)
        print(f"  📸 Screenshot captured, calling {model}...")

        action = call_vision_model(messages, api_base, model, api_key)
        act_type = action.get("action", "?")
        print(f"  🎯 Action: {act_type} {action.get('params', {})}")

        # 3. Execute
        result = execute_action(action)
        print(f"  📋 Result: {result}")

        # 4. Record history
        history.append({"role": "assistant", "content": json.dumps(action)})
        history.append({"role": "user", "content": f"Action result: {result}"})

        # 5. Check completion
        if act_type == "done":
            print(f"\n✅ Task completed: {result}")
            return 0
        elif act_type == "fail":
            print(f"\n❌ Task failed: {result}")
            return 1

        # 6. Wait before next step
        time.sleep(delay)

    print(f"\n⏰ Max steps ({max_steps}) reached without completion")
    return 2


def main():
    parser = argparse.ArgumentParser(description="Adaptive Vision Agent for GUI automation")
    parser.add_argument("task", help="Task description in natural language")
    parser.add_argument("--model", default="moondream", help="Vision model name (default: moondream)")
    parser.add_argument("--api-base", default="http://localhost:11434/v1", help="API base URL")
    parser.add_argument("--api-key", default="", help="API key (if needed)")
    parser.add_argument("--max-steps", type=int, default=20, help="Max steps")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between steps (seconds)")
    args = parser.parse_args()

    return run_agent(
        task=args.task,
        api_base=args.api_base,
        model=args.model,
        api_key=args.api_key,
        max_steps=args.max_steps,
        delay=args.delay,
    )


if __name__ == "__main__":
    sys.exit(main())
