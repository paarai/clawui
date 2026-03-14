#!/usr/bin/env python3
"""Light CDP smoke test.

Marked as integration because it requires a graphical desktop + Chromium.
"""

import base64
import os
import time

import pytest

from src.cdp_helper import launch_chromium_with_cdp, CDPClient


def _has_display() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


@pytest.mark.integration
@pytest.mark.skipif(not _has_display(), reason="No display server")
def test_cdp_smoke(tmp_path):
    proc = launch_chromium_with_cdp()
    if not proc:
        pytest.skip("Could not launch Chromium with CDP")

    try:
        time.sleep(3)
        client = CDPClient()
        if not client.is_available():
            pytest.skip("CDP endpoint unavailable")

        assert client.navigate("https://example.com"), "CDP navigate failed"
        time.sleep(2)

        title = (client.get_page_title() or "").lower()
        url = (client.get_page_url() or "").lower()
        assert "example" in (title + url), f"Unexpected page: {title} @ {url}"

        result = client.evaluate("document.querySelector('h1') !== null")
        value = result.get("result", {}).get("value") if isinstance(result, dict) else None
        assert value is True, f"Expected h1 on page, got: {result}"

        b64 = client.take_screenshot()
        assert b64, "Screenshot returned empty payload"

        png_bytes = base64.b64decode(b64)
        shot = tmp_path / "cdp_smoke.png"
        shot.write_bytes(png_bytes)
        assert shot.stat().st_size > 0, "Decoded screenshot is empty"
    finally:
        proc.terminate()
