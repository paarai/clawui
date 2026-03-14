#!/usr/bin/env python3
"""Core test suite for ClawUI - validates tool registration, backends, and basic operations."""

import os
import sys
import time

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0
SKIP = 0

def run_test(name, fn):
    global PASS, FAIL, SKIP
    try:
        result = fn()
        if result == "SKIP":
            print(f"  ⏭️  {name}: SKIP")
            SKIP += 1
        else:
            print(f"  ✅ {name}: PASS")
            PASS += 1
    except Exception as e:
        print(f"  ❌ {name}: FAIL - {e}")
        FAIL += 1


# === Tool Registration ===
def test_tool_count():
    from src.agent import create_tools
    tools = create_tools()
    assert len(tools) >= 45, f"Expected >=45 tools, got {len(tools)}"


def test_no_duplicate_tools():
    from src.agent import create_tools
    tools = create_tools()
    names = [t["name"] for t in tools]
    dupes = [n for n in set(names) if names.count(n) > 1]
    assert not dupes, f"Duplicate tools: {dupes}"


def test_all_tools_have_schema():
    from src.agent import create_tools
    tools = create_tools()
    for t in tools:
        assert "name" in t, f"Tool missing name: {t}"
        assert "description" in t, f"Tool {t['name']} missing description"
        assert "input_schema" in t, f"Tool {t['name']} missing input_schema"


def test_wait_for_element_registered():
    from src.agent import create_tools
    tools = create_tools()
    names = [t["name"] for t in tools]
    assert "wait_for_element" in names, "wait_for_element tool not registered"



# === Backend Imports ===
def test_atspi_import():
    from src.atspi_helper import list_applications, get_ui_tree_summary, find_elements


def test_x11_import():
    from src.x11_helper import list_windows


def test_cdp_import():
    from src.cdp_helper import CDPClient


def test_cdp_wait_for_selector_result_parsing():
    """wait_for_selector should correctly parse Runtime.evaluate nested result.value payload."""
    from src.cdp_helper import CDPClient
    c = CDPClient()
    c.evaluate = lambda _expr: {"result": {"type": "object", "value": {"found": True, "text": "Submit", "tag": "BUTTON"}}}
    r = c.wait_for_selector("button", timeout=0.1, poll_interval=0.01)
    assert r.get("found") is True, f"Expected found=True, got {r}"
    assert r.get("text") == "Submit", f"Expected text='Submit', got {r}"


def test_cdp_wait_for_load_ready_state_nested_result():
    """CDPBackend.wait_for_load should handle nested Runtime.evaluate payloads."""
    from src.cdp_backend import CDPBackend

    backend = CDPBackend.__new__(CDPBackend)
    backend._ensure_connection = lambda: None

    class DummyClient:
        def evaluate(self, _expr):
            return {"result": {"value": "complete"}}

    backend.client = DummyClient()
    assert backend.wait_for_load(timeout=0.2, poll_interval=0.01) is True


def test_cdp_wait_for_load_timeout_returns_false():
    """CDPBackend.wait_for_load should return False on timeout when page never completes."""
    from src.cdp_backend import CDPBackend

    backend = CDPBackend.__new__(CDPBackend)
    backend._ensure_connection = lambda: None

    class DummyClient:
        def evaluate(self, _expr):
            return {"result": {"value": "loading"}}

    backend.client = DummyClient()
    assert backend.wait_for_load(timeout=0.05, poll_interval=0.01) is False


def test_marionette_import():
    from src.marionette_helper import MarionetteClient


def test_perception_import():
    from src.perception import list_applications, get_ui_tree_summary


def test_ocr_import():
    from src.ocr_tool import ocr_find_text


def test_recorder_import():
    from src.recorder import Recorder, Player



# === AT-SPI Backend (requires desktop session) ===
def test_atspi_list_apps():
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        import pytest; pytest.skip("No display")
    from src.atspi_helper import list_applications
    apps = list_applications()
    # Should find at least something in a desktop session
    assert isinstance(apps, (list, str)), f"Unexpected type: {type(apps)}"


def test_atspi_ui_tree():
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        import pytest; pytest.skip("No display")
    from src.atspi_helper import get_ui_tree_summary
    tree = get_ui_tree_summary(max_depth=2)
    assert tree is not None, "UI tree returned None"



# === X11 Backend ===
def test_x11_list_windows():
    if not os.environ.get("DISPLAY"):
        import pytest; pytest.skip("No display")
    from src.x11_helper import list_windows
    windows = list_windows()
    assert isinstance(windows, list), f"Expected list, got {type(windows)}"



# === Screenshot ===
def test_screenshot():
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        import pytest; pytest.skip("No display")
    from src.screenshot import take_screenshot
    img = take_screenshot()
    assert img and len(img) > 100, "Screenshot too small or empty"


def test_screen_size():
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        import pytest; pytest.skip("No display")
    from src.screenshot import get_screen_size
    w, h = get_screen_size()
    assert w > 0 and h > 0, f"Invalid screen size: {w}x{h}"



# === Tool Execution (safe tools only) ===
def test_execute_ui_tree():
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        import pytest; pytest.skip("No display")
    from src.agent import execute_tool
    result = execute_tool("ui_tree", {})
    assert "type" in result, f"Missing 'type' in result: {result}"


def test_execute_list_windows():
    if not os.environ.get("DISPLAY"):
        import pytest; pytest.skip("No display")
    from src.agent import execute_tool
    result = execute_tool("list_windows", {})
    assert "type" in result, f"Missing 'type' in result: {result}"


def test_execute_find_element_no_match():
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        import pytest; pytest.skip("No display")
    from src.agent import execute_tool
    result = execute_tool("find_element", {"name": "__nonexistent_element_12345__"})
    assert "type" in result, f"Missing 'type' in result"


def test_execute_wait_for_element_timeout():
    """wait_for_element should timeout quickly for nonexistent element."""
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        import pytest; pytest.skip("No display")
    from src.agent import execute_tool
    start = time.time()
    result = execute_tool("wait_for_element", {"name_contains": "__nonexistent__", "timeout": 2})
    elapsed = time.time() - start
    assert "Timeout" in result.get("text", ""), f"Expected timeout, got: {result}"
    assert elapsed < 10, f"Took too long: {elapsed:.1f}s (expected ~2s timeout + AT-SPI overhead)"



# === Perception Router ===
def test_perception_routing():
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        import pytest; pytest.skip("No display")
    from src.perception import list_applications
    apps = list_applications()
    assert apps is not None, "Perception list_applications returned None"



# === Firefox Marionette Backend ===
def test_marionette_smoke():
    """Smoke test: connect to Firefox Marionette, navigate, get title."""
    # Only run if DISPLAY is available (requires GUI session)
    if not os.environ.get("DISPLAY"):
        import pytest; pytest.skip("No display")
    from src.marionette_helper import get_or_create_marionette_client
    client = get_or_create_marionette_client()
    if not client or not client.is_available():
        import pytest; pytest.skip("No display")  # Firefox not running with --marionette
    try:
        session = client.new_session()
        if not session:
            import pytest; pytest.skip("No display")
        client.navigate("https://example.com")
        # Wait a bit for load
        time.sleep(2)
        title = client.get_title() or ""
        url = client.get_url() or ""
        assert "example" in title.lower() or "example" in url.lower(), f"Unexpected page: {title} / {url}"
        # Clean up: close window (session remains reusable)
        try:
            client.close_window()
        except:
            pass
    
    except Exception as e:
        # Any failure is a test failure (not skip) because it indicates broken backend
        raise AssertionError(f"Marionette smoke test failed: {e}") from e


if __name__ == "__main__":
    print("=" * 60)
    print("ClawUI Core Test Suite")
    print("=" * 60)

    print("\n📦 Tool Registration:")
    run_test("tool count >= 45", test_tool_count)
    run_test("no duplicate tools", test_no_duplicate_tools)
    run_test("all tools have schema", test_all_tools_have_schema)
    run_test("wait_for_element registered", test_wait_for_element_registered)

    print("\n📥 Backend Imports:")
    run_test("AT-SPI import", test_atspi_import)
    run_test("X11 import", test_x11_import)
    run_test("CDP import", test_cdp_import)
    run_test("CDP wait_for_selector result parsing", test_cdp_wait_for_selector_result_parsing)
    run_test("CDP wait_for_load nested result", test_cdp_wait_for_load_ready_state_nested_result)
    run_test("CDP wait_for_load timeout", test_cdp_wait_for_load_timeout_returns_false)
    run_test("Marionette import", test_marionette_import)
    run_test("Perception import", test_perception_import)
    run_test("OCR import", test_ocr_import)
    run_test("Recorder import", test_recorder_import)

    print("\n🖥️  AT-SPI Backend:")
    run_test("list applications", test_atspi_list_apps)
    run_test("UI tree", test_atspi_ui_tree)

    print("\n🪟 X11 Backend:")
    run_test("list windows", test_x11_list_windows)

    print("\n🌐 Firefox Marionette Backend:")
    run_test("Marionette smoke test", test_marionette_smoke)

    print("\n📸 Screenshot:")
    run_test("take screenshot", test_screenshot)
    run_test("screen size", test_screen_size)

    print("\n🔧 Tool Execution:")
    run_test("execute ui_tree", test_execute_ui_tree)
    run_test("execute list_windows", test_execute_list_windows)
    run_test("execute find_element (no match)", test_execute_find_element_no_match)
    run_test("execute wait_for_element (timeout)", test_execute_wait_for_element_timeout)

    print("\n🔀 Perception Router:")
    run_test("perception routing", test_perception_routing)

    print("\n" + "=" * 60)
    total = PASS + FAIL + SKIP
    print(f"Results: {PASS}/{total} passed, {FAIL} failed, {SKIP} skipped")
    print("=" * 60)
    sys.exit(1 if FAIL > 0 else 0)
