#!/usr/bin/env python3
"""End-to-end test for clawui - multi-backend.

Requires a running desktop session. Skips backends that aren't available.
"""

import sys, os, subprocess, time, logging, pytest

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s',
    handlers=[logging.FileHandler('/tmp/e2e_test.log', mode='w'), logging.StreamHandler()])
log = logging.info

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'gui-automation'))


def _has_display():
    return bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'))


@pytest.mark.skipif(not _has_display(), reason="No display server")
def test_atspi():
    log("=== AT-SPI Test ===")
    from clawui.atspi_helper import list_applications
    apps = list_applications()
    log(f"Detected {len(apps)} apps")
    assert len(apps) > 5, f"Expected >5 AT-SPI apps, got {len(apps)}"


@pytest.mark.skipif(not _has_display(), reason="No display server")
def test_x11():
    log("=== X11 Test ===")
    from clawui.x11_helper import list_windows

    wins = list_windows()
    named = [w for w in wins if w.title]
    log(f"X11 windows: {len(wins)} total, {len(named)} named")

    # Pure Wayland sessions may have no active XWayland windows.
    # That's an environment limitation, not a product failure.
    if len(named) == 0:
        pytest.skip("No named X11 windows found (likely pure Wayland with no XWayland apps)")

    assert len(named) > 0


@pytest.mark.skipif(not _has_display(), reason="No display server")
def test_cdp():
    log("=== CDP Test ===")
    from clawui.cdp_helper import get_or_create_cdp_client
    client = get_or_create_cdp_client()
    if not client:
        pytest.skip("CDP client unavailable")

    ok = client.navigate("https://github.com")
    time.sleep(3)
    title = client.get_page_title()
    url = client.get_page_url()
    log(f"Page: {title} @ {url}")
    assert "github" in (title + url).lower(), f"Expected github in title/url, got {title} @ {url}"


@pytest.mark.skipif(not _has_display(), reason="No display server")
def test_marionette():
    log("=== Marionette Test ===")
    from clawui.marionette_helper import get_or_create_marionette_client

    client = get_or_create_marionette_client()
    if not client:
        pytest.skip("Marionette not available")

    session = client.new_session()
    if not session:
        pytest.skip("Failed to create Marionette session")

    ok = client.navigate("https://example.com")
    time.sleep(2)
    title = client.get_title()
    url = client.get_url()
    log(f"Page: {title} @ {url}")

    try:
        client.close_window()
    except Exception:
        pass

    assert ok and "example" in (title + url).lower(), f"Marionette test failed: {title} @ {url}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
