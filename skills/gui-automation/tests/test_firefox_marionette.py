#!/usr/bin/env python3
"""Firefox Marionette reliability test - validates core browser automation."""

import sys
import os
import time
import logging

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
log = logging.info

# Setup paths
sys.path.insert(0, '/home/hung/.openclaw/workspace/ClawUI/skills/gui-automation')
from src.marionette_helper import get_or_create_marionette_client


def wait_for_page_load(client, timeout=10):
    """Wait for page to fully load and return title/url."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            title = client.get_title() or ""
            url = client.get_url() or ""
            if title and url and "about:blank" not in url.lower():
                return title, url
        except:
            pass
        time.sleep(0.5)
    return client.get_title() or "", client.get_url() or ""


def with_fresh_client(test_func):
    """Decorator: create fresh client/session for each test."""
    def wrapper():
        client = None
        try:
            # Quit any existing session
            try:
                old = get_or_create_marionette_client()
                if old:
                    old.quit()
            except:
                pass
            time.sleep(1)

            client = get_or_create_marionette_client()
            assert client, "No Marionette client"
            session = client.new_session()
            assert session, "Failed to create session"
            log(f"   [Session: {session[:8]}]")
            return test_func(client)
        finally:
            if client:
                try:
                    client.close_window()
                except:
                    pass
    return wrapper


@with_fresh_client
def test_basic(client):
    """Basic navigation and page info."""
    log("1. Basic navigation...")
    client.navigate("https://example.com")
    title, url = wait_for_page_load(client)
    log(f"   Loaded: {title} @ {url}")
    assert "example" in title.lower() or "example" in url.lower(), "Wrong page"
    log("   ✅ PASSED")
    return True


@with_fresh_client
def test_form_interaction(client):
    """Test form fill and button click."""
    log("2. Form interaction...")
    client.navigate("https://the-internet.herokuapp.com/login")

    # Wait for page to load
    title, url = wait_for_page_load(client)
    log(f"   Page title: '{title}'")
    time.sleep(1)  # Extra wait for DOM

    # Find username - check page content first
    result = client.execute_script("return document.title + '|' + document.readyState;")
    log(f"   JS state: {result}")

    username = client.find_element("id", "username")
    assert username, "Username field not found"
    client.send_keys(username, "tomsmith")
    log("   Typed username")

    password = client.find_element("id", "password")
    assert password, "Password field not found"
    client.send_keys(password, "SuperSecretPassword!")
    log("   Typed password")

    btn = client.find_element("css selector", "button[type='submit']")
    assert btn, "Login button not found"
    client.click_element(btn)
    log("   Clicked login")

    time.sleep(2)
    title, url = wait_for_page_load(client)
    log(f"   After login: {title}")
    assert "secure" in title.lower() or "secure" in url.lower(), f"Login failed: {title}"
    log("   ✅ PASSED")
    return True


@with_fresh_client
def test_screenshot(client):
    """Test screenshot capture."""
    log("3. Screenshot...")
    client.navigate("https://example.com")
    wait_for_page_load(client)
    time.sleep(1)

    b64 = client.take_screenshot()
    assert b64, "Screenshot empty"
    assert len(b64) > 5000, f"Screenshot too small: {len(b64)} bytes"

    screenshot_dir = os.path.join(os.path.dirname(__file__), "screenshots/firefox_marionette")
    os.makedirs(screenshot_dir, exist_ok=True)
    path = os.path.join(screenshot_dir, f"scr_{int(time.time())}.png")
    with open(path, "wb") as f:
        f.write(__import__('base64').b64decode(b64))
    log(f"   Saved: {path} ({len(b64)} bytes)")

    log("   ✅ PASSED")
    return True


@with_fresh_client
def test_js_execution(client):
    """Test JavaScript execution."""
    log("4. JavaScript...")
    result = client.execute_script("return 2 + 2;")
    assert result == 4, f"JS math: {result}"

    info = client.execute_script("return { t: document.title, u: location.href };")
    assert info.get("t"), "No title from JS"
    log(f"   Page: {info.get('t')}")

    log("   ✅ PASSED")
    return True


def main():
    log("Firefox Marionette Test Suite")
    log("=" * 50)

    tests = [test_basic, test_form_interaction, test_screenshot, test_js_execution]

    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            log(f"   ❌ FAILED: {e}")

    log("=" * 50)
    log(f"Results: {passed}/{len(tests)} passed")

    if passed == len(tests):
        log("✅ ALL TESTS PASSED")
    else:
        log(f"❌ {len(tests)-passed} FAILED")

    # Keep Firefox running
    log("Firefox left running for reuse")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    sys.exit(main())
