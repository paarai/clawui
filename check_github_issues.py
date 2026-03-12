#!/usr/bin/env python3
"""
Robust GitHub issues checker for ClawUI continuous improvement.

Tries multiple methods in order:
1. GitHub API via GITHUB_TOKEN environment variable.
2. GitHub CLI (gh) if authenticated.
3. CDP browser fallback: navigate to issues page and take screenshot.

Exits 0 if any method succeeds; prints useful output or screenshot path.
"""

import os
import sys
import subprocess
import time
import json
import base64

# Add skill path for CDP
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'skills/gui-automation'))

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def method_api_token():
    """Try GitHub API using GITHUB_TOKEN."""
    token = os.getenv('GITHUB_TOKEN', '').strip()
    if not token:
        return False, "GITHUB_TOKEN not set"
    repo = "longgo1001/clawui"
    url = f"https://api.github.com/repos/{repo}/issues?state=open&per_page=50"
    try:
        result = subprocess.run(
            ['curl', '-s', '-H', f'Authorization: token {token}', url],
            capture_output=True, text=True, timeout=10, check=True
        )
        data = json.loads(result.stdout)
        print(f"GitHub API: {len(data)} open issues")
        for i, issue in enumerate(data[:10], 1):
            print(f"#{issue['number']}: {issue['title'][:70]}")
        return True, "API success"
    except subprocess.CalledProcessError as e:
        return False, f"API curl failed: {e}"
    except json.JSONDecodeError as e:
        return False, f"API JSON parse error: {e}"

def method_gh_cli():
    """Try GitHub CLI if authenticated."""
    try:
        # Check auth
        subprocess.run(['gh', 'auth', 'status'], check=True, capture_output=True)
        # List issues
        out = subprocess.run(
            ['gh', 'issue', 'list', '--repo', 'longgo1001/clawui', '--state', 'open', '--limit', '10'],
            capture_output=True, text=True, timeout=15, check=True
        ).stdout.strip()
        if out:
            print("GitHub CLI issues:")
            print(out)
        else:
            print("No open issues (gh CLI).")
        return True, "gh CLI success"
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return False, f"gh CLI not available or not authenticated: {e}"

def method_cdp_fallback():
    """Use CDP to navigate, screenshot, and vision-extract issues."""
    try:
        # Use the proper import path for the CDP client from the skill
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ClawUI/skills/gui-automation'))
        from src.cdp_helper import get_or_create_cdp_client
    except ImportError as e:
        return False, f"CDP import failed: {e}"

    screenshot_dir = os.path.join(os.path.dirname(__file__), "screenshots/gh_issues")
    os.makedirs(screenshot_dir, exist_ok=True)
    screenshot_path = os.path.join(screenshot_dir, f"issues_{int(time.time())}.png")

    # Use the unified client getter which will auto-launch if needed
    client = get_or_create_cdp_client()
    if not client:
        return False, "No CDP browser available and auto-launch failed"

    try:
        client.navigate("https://github.com/longgo1001/clawui/issues")
        time.sleep(3)  # Wait for page to load
        b64 = client.take_screenshot()
        if not b64:
            return False, "Screenshot returned no data"
        png = base64.b64decode(b64)
        with open(screenshot_path, "wb") as f:
            f.write(png)
        print(f"CDP fallback: screenshot saved to {screenshot_path}")

        # Attempt vision-based extraction
        try:
            # Reuse the skill's vision backend if available
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ClawUI/skills/gui-automation'))
            from src.vision_backend import VisionBackend
            vb = VisionBackend()
            prompt = "List all open GitHub issues from this screenshot. For each issue, output exactly: '#<number>: <title>' on its own line. If none, say 'No open issues.'"
            messages = [
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": vb._encode_image(b64)}}
                ]}
            ]
            resp = vb.chat(messages, tools=[], system="You are a helpful assistant that extracts issue data from GitHub screenshots.")
            text = resp.get("text", "").strip()
            print("Vision analysis of issues page:")
            print(text)
            return True, "CDP+vision extracted issues"
        except Exception as e:
            print(f"Vision extraction failed: {e}")
            print("Falling back to manual screenshot review.")
            return True, "CDP screenshot only (vision failed)"
    except Exception as e:
        return False, f"CDP error: {e}"

def main():
    log("Checking GitHub issues...")
    methods = [
        ("GitHub API", method_api_token),
        ("GitHub CLI", method_gh_cli),
        ("CDP Fallback", method_cdp_fallback),
    ]
    for name, func in methods:
        success, msg = func()
        log(f"{name}: {'✅' if success else '❌'} {msg}")
        if success:
            return 0
    # All failed
    log("All methods failed.")
    return 1

if __name__ == "__main__":
    sys.exit(main())
