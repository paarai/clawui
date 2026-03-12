#!/usr/bin/env python3
"""
ClawUI System Health Check (Reliability-Optimized)

Verifies all automation backends are available and functional without
auto-launching browsers (to avoid hangs in cron/headless environments).

Exit codes: 0 = all healthy, 1 = some checks failed, 2 = critical failure.
"""

import sys
import os
import subprocess
import time
import json
import socket
import http.client

# Determine ClawUI root (assuming this script is in ClawUI/tools/)
script_dir = os.path.dirname(os.path.abspath(__file__))
clawui_root = os.path.dirname(script_dir)  # go up from tools/ to ClawUI/
sys.path.insert(0, os.path.join(clawui_root, 'skills', 'gui-automation'))

def section(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)

def ok(msg):
    print(f"✅ {msg}")
    return True

def fail(msg):
    print(f"❌ {msg}")
    return False

def check_atspi():
    """Check AT-SPI backend."""
    try:
        import pyatspi
        desktop = pyatspi.Registry.getDesktop(0)
        if desktop:
            return ok("AT-SPI accessible (pyatspi)")
    except ImportError:
        return fail("AT-SPI not available (pyatspi not installed)")
    except Exception as e:
        return fail(f"AT-SPI error: {e}")

def check_x11():
    """Check X11 backend (xdotool and Xlib)."""
    checks = []
    try:
        subprocess.run(['xdotool', '--version'], capture_output=True, check=True, timeout=2)
        checks.append(ok("xdotool available"))
    except Exception as e:
        checks.append(fail(f"xdotool not found: {e}"))

    try:
        import Xlib
        checks.append(ok("python-xlib available"))
    except ImportError:
        checks.append(fail("python-xlib not installed"))

    try:
        from src.x11_helper import list_windows
        windows = list_windows()
        if windows is not None:
            checks.append(ok(f"X11 window enumeration works ({len(windows)} windows)"))
        else:
            checks.append(fail("X11 list_windows returned None"))
    except Exception as e:
        checks.append(fail(f"X11 helper error: {e}"))

    return all(checks)

def check_cdp():
    """Check CDP backend without auto-launching (safe for cron)."""
    try:
        from src.cdp_helper import CDPClient
        client = CDPClient()
        # Quick HTTP GET to /json/version with short timeout
        try:
            conn = http.client.HTTPConnection(client.host, client.port, timeout=2)
            conn.request("GET", "/json/version")
            resp = conn.getresponse()
            if resp.status == 200:
                data = json.loads(resp.read())
                product = data.get('product', 'Chromium')
                return ok(f"CDP available - {product}")
            else:
                return fail(f"CDP endpoint responded {resp.status}")
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            return fail(f"CDP not running (connection failed: {type(e).__name__})")
        except json.JSONDecodeError:
            return fail("CDP response not valid JSON")
    except Exception as e:
        return fail(f"CDP check error: {e}")

def check_marionette():
    """Check Marionette backend without auto-launching (safe for cron)."""
    try:
        from src.marionette_helper import MarionetteClient
        client = MarionetteClient()
        # Simple socket connect with short timeout
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((client.host, client.port))
            sock.close()
            if result == 0:
                return ok("Marionette port open (Firefox with --marionette running)")
            else:
                return fail(f"Marionette not listening (connect error code {result})")
        except socket.timeout:
            return fail("Marionette connection timeout")
        except OSError as e:
            return fail(f"Marionette socket error: {e}")
    except Exception as e:
        return fail(f"Marionette check error: {e}")

def check_vision():
    """Check vision backend (Ollama/OpenAI)."""
    try:
        from src.vision_backend import VisionBackend
        # Check Ollama endpoint
        try:
            import httpx
            client = httpx.Client(timeout=httpx.Timeout(3.0))
            resp = client.get("http://localhost:11434/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                if models:
                    return ok(f"Ollama available - models: {', '.join(models[:3])}")
                else:
                    return fail("Ollama running but no models downloaded")
            else:
                return fail(f"Ollama responded {resp.status_code}")
        except httpx.RequestError:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                return ok("OpenAI API key configured")
            else:
                return fail("No vision backend: Ollama not responding and OPENAI_API_KEY not set")
    except Exception as e:
        return fail(f"Vision backend error: {e}")

def check_ollama_service():
    """Check if ollama service is running."""
    try:
        subprocess.run(['pgrep', '-f', 'ollama'], capture_output=True, check=True)
        return ok("Ollama service running")
    except subprocess.CalledProcessError:
        return fail("Ollama service not running")

def main():
    section("ClawUI System Health Check")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Host: {os.uname().nodename if hasattr(os,'uname') else 'unknown'}")

    results = []

    section("1. AT-SPI Backend (Wayland native apps)")
    results.append(check_atspi())

    section("2. X11 Backend (XWayland apps)")
    results.append(check_x11())

    section("3. CDP Backend (Chromium/Chrome)")
    results.append(check_cdp())

    section("4. Marionette Backend (Firefox)")
    results.append(check_marionette())

    section("5. Vision Backend")
    results.append(check_vision())

    section("6. Ollama Service")
    results.append(check_ollama_service())

    section("Summary")
    total = len(results)
    passed = sum(results)
    print(f"Checks passed: {passed}/{total}")
    if passed == total:
        print("🎉 All systems go!")
        return 0
    elif passed >= total - 1:
        print("⚠️  Minor issues detected")
        return 1
    else:
        print("🚨 Critical issues detected")
        return 2

if __name__ == "__main__":
    sys.exit(main())
