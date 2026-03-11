#!/usr/bin/env python3
"""End-to-end test for clawui - multi-backend."""

import sys, os, subprocess, time, logging

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s',
    handlers=[logging.FileHandler('/tmp/e2e_test.log', mode='w'), logging.StreamHandler()])
log = logging.info

sys.path.insert(0, '/home/hung/.openclaw/workspace/skills/gui-automation')
from src.x11_helper import list_windows, find_windows_by_class, activate_window
from src.cdp_helper import CDPClient, get_or_create_cdp_client
from src.marionette_helper import MarionetteClient

def test_atspi():
    log("=== AT-SPI Test ===")
    from src.atspi_helper import list_applications
    apps = list_applications()
    log(f"Detected {len(apps)} apps")
    return len(apps) > 5

def test_x11():
    log("=== X11 Test ===")
    wins = list_windows()
    named = [w for w in wins if w.title]
    log(f"X11 windows: {len(wins)} total, {len(named)} named")
    return len(named) > 0

def test_cdp():
    log("=== CDP Test ===")
    # Check if Chromium already running with CDP
    client = CDPClient()
    if not client.is_available():
        log("Chromium CDP not available, launching...")
        subprocess.Popen(['snap', 'run', 'chromium',
            '--remote-debugging-port=9222', '--remote-allow-origins=*',
            '--no-first-run', 'about:blank'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(5)
        if not client.is_available():
            log("Failed to launch Chromium with CDP")
            return False

    # Navigate
    ok = client.navigate("https://github.com")
    time.sleep(3)
    title = client.get_page_title()
    url = client.get_page_url()
    log(f"Page: {title} @ {url}")
    return "github" in (title + url).lower()

def test_marionette():
    log("=== Marionette Test ===")
    client = MarionetteClient()
    if not client.is_available():
        log("Marionette not available (is Firefox running with --marionette?)")
        return False
    session = client.new_session()
    if not session:
        log("Failed to create Marionette session")
        return False
    ok = client.navigate("https://example.com")
    time.sleep(2)
    title = client.get_title()
    url = client.get_url()
    log(f"Page: {title} @ {url}")
    ok = ok and ("example" in (title + url).lower())
    try:
        client.close_window()
    except Exception:
        pass
    return ok

def main():
    results = [
        ("AT-SPI", test_atspi()),
        ("X11", test_x11()),
        ("CDP", test_cdp()),
        ("Marionette", test_marionette()),
    ]
    log("\n=== Summary ===")
    for name, ok in results:
        log(f"  {name}: {'PASS' if ok else 'FAIL'}")
    return 0 if all(ok for _, ok in results) else 1

if __name__ == "__main__":
    sys.exit(main())
