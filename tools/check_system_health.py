#!/usr/bin/env python3
"""
ClawUI System Health Check

Verifies all automation backends are available and functional.
Exit codes: 0 = all healthy, 1 = some checks failed, 2 = critical failure.
"""

import sys
import os
import subprocess
import time
import json

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
        # Try to get desktop
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
    # xdotool
    try:
        subprocess.run(['xdotool', '--version'], capture_output=True, check=True, timeout=2)
        checks.append(ok("xdotool available"))
    except Exception as e:
        checks.append(fail(f"xdotool not found: {e}"))

    # X11 python module
    try:
        import Xlib
        checks.append(ok("python-xlib available"))
    except ImportError:
        checks.append(fail("python-xlib not installed"))

    # Try listing windows
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
    """Check CDP backend (Chromium)."""
    try:
        from src.cdp_helper import get_or_create_cdp_client
        client = get_or_create_cdp_client()
        if client and client.is_available():
            info = {"url": client.get_page_url() or "", "title": client.get_page_title() or ""}
            return ok(f"CDP available - browser ready ({info.get('title','')})")
        else:
            return fail("CDP client not available (no browser)")
    except Exception as e:
        return fail(f"CDP error: {e}")

def check_marionette():
    """Check Marionette backend (Firefox)."""
    try:
        from src.marionette_helper import get_or_create_marionette_client
        # Don't auto-start for health check - just check if any running instance responds
        client = get_or_create_marionette_client()
        if client:
            try:
                title = client.get_title() or ""
                url = client.get_url() or ""
                return ok(f"Marionette connected - Firefox ready ({title})")
            except:
                return fail("Marionette client exists but not responding")
        else:
            return fail("Marionette not available (Firefox not running with --marionette)")
    except Exception as e:
        return fail(f"Marionette error: {e}")

def check_vision():
    """Check vision backend (Ollama/OpenAI)."""
    try:
        from src.vision_backend import VisionBackend
        # Check Ollama endpoint if default
        import httpx
        client = httpx.Client(timeout=httpx.Timeout(3.0))
        try:
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
            # Not Ollama, maybe OpenAI?
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
    # Debug: show import paths
    print(f"Debug: sys.path includes: {sys.path[:3]}")

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