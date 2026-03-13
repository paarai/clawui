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

def test(name, fn):
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
    return True

def test_no_duplicate_tools():
    from src.agent import create_tools
    tools = create_tools()
    names = [t["name"] for t in tools]
    dupes = [n for n in set(names) if names.count(n) > 1]
    assert not dupes, f"Duplicate tools: {dupes}"
    return True

def test_all_tools_have_schema():
    from src.agent import create_tools
    tools = create_tools()
    for t in tools:
        assert "name" in t, f"Tool missing name: {t}"
        assert "description" in t, f"Tool {t['name']} missing description"
        assert "input_schema" in t, f"Tool {t['name']} missing input_schema"
    return True

def test_wait_for_element_registered():
    from src.agent import create_tools
    tools = create_tools()
    names = [t["name"] for t in tools]
    assert "wait_for_element" in names, "wait_for_element tool not registered"
    return True


# === Backend Imports ===
def test_atspi_import():
    from src.atspi_helper import list_applications, get_ui_tree_summary, find_elements
    return True

def test_x11_import():
    from src.x11_helper import list_windows
    return True

def test_cdp_import():
    from src.cdp_helper import CDPClient
    return True

def test_marionette_import():
    from src.marionette_helper import MarionetteClient
    return True

def test_perception_import():
    from src.perception import list_applications, get_ui_tree_summary
    return True

def test_ocr_import():
    from src.ocr_tool import ocr_find_text
    return True

def test_recorder_import():
    from src.recorder import Recorder, Player
    return True


# === AT-SPI Backend (requires desktop session) ===
def test_atspi_list_apps():
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return "SKIP"
    from src.atspi_helper import list_applications
    apps = list_applications()
    # Should find at least something in a desktop session
    assert isinstance(apps, (list, str)), f"Unexpected type: {type(apps)}"
    return True

def test_atspi_ui_tree():
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return "SKIP"
    from src.atspi_helper import get_ui_tree_summary
    tree = get_ui_tree_summary(max_depth=2)
    assert tree is not None, "UI tree returned None"
    return True


# === X11 Backend ===
def test_x11_list_windows():
    if not os.environ.get("DISPLAY"):
        return "SKIP"
    from src.x11_helper import list_windows
    windows = list_windows()
    assert isinstance(windows, list), f"Expected list, got {type(windows)}"
    return True


# === Screenshot ===
def test_screenshot():
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return "SKIP"
    from src.screenshot import take_screenshot
    img = take_screenshot()
    assert img and len(img) > 100, "Screenshot too small or empty"
    return True

def test_screen_size():
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return "SKIP"
    from src.screenshot import get_screen_size
    w, h = get_screen_size()
    assert w > 0 and h > 0, f"Invalid screen size: {w}x{h}"
    return True


# === Tool Execution (safe tools only) ===
def test_execute_ui_tree():
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return "SKIP"
    from src.agent import execute_tool
    result = execute_tool("ui_tree", {})
    assert "type" in result, f"Missing 'type' in result: {result}"
    return True

def test_execute_list_windows():
    if not os.environ.get("DISPLAY"):
        return "SKIP"
    from src.agent import execute_tool
    result = execute_tool("list_windows", {})
    assert "type" in result, f"Missing 'type' in result: {result}"
    return True

def test_execute_find_element_no_match():
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return "SKIP"
    from src.agent import execute_tool
    result = execute_tool("find_element", {"name": "__nonexistent_element_12345__"})
    assert "type" in result, f"Missing 'type' in result"
    return True

def test_execute_wait_for_element_timeout():
    """wait_for_element should timeout quickly for nonexistent element."""
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return "SKIP"
    from src.agent import execute_tool
    start = time.time()
    result = execute_tool("wait_for_element", {"name_contains": "__nonexistent__", "timeout": 2})
    elapsed = time.time() - start
    assert "Timeout" in result.get("text", ""), f"Expected timeout, got: {result}"
    assert elapsed < 5, f"Took too long: {elapsed:.1f}s"
    return True


# === Perception Router ===
def test_perception_routing():
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return "SKIP"
    from src.perception import list_applications
    apps = list_applications()
    assert apps is not None, "Perception list_applications returned None"
    return True


# === Firefox Marionette Backend ===
def test_marionette_smoke():
    """Smoke test: connect to Firefox Marionette, navigate, get title."""
    # Only run if DISPLAY is available (requires GUI session)
    if not os.environ.get("DISPLAY"):
        return "SKIP"
    from src.marionette_helper import get_or_create_marionette_client
    client = get_or_create_marionette_client()
    if not client or not client.is_available():
        return "SKIP"  # Firefox not running with --marionette
    try:
        session = client.new_session()
        if not session:
            return "SKIP"
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
        return True
    except Exception as e:
        # Any failure is a test failure (not skip) because it indicates broken backend
        raise AssertionError(f"Marionette smoke test failed: {e}") from e


if __name__ == "__main__":
    print("=" * 60)
    print("ClawUI Core Test Suite")
    print("=" * 60)

    print("\n📦 Tool Registration:")
    test("tool count >= 45", test_tool_count)
    test("no duplicate tools", test_no_duplicate_tools)
    test("all tools have schema", test_all_tools_have_schema)
    test("wait_for_element registered", test_wait_for_element_registered)

    print("\n📥 Backend Imports:")
    test("AT-SPI import", test_atspi_import)
    test("X11 import", test_x11_import)
    test("CDP import", test_cdp_import)
    test("Marionette import", test_marionette_import)
    test("Perception import", test_perception_import)
    test("OCR import", test_ocr_import)
    test("Recorder import", test_recorder_import)

    print("\n🖥️  AT-SPI Backend:")
    test("list applications", test_atspi_list_apps)
    test("UI tree", test_atspi_ui_tree)

    print("\n🪟 X11 Backend:")
    test("list windows", test_x11_list_windows)

    print("\n🌐 Firefox Marionette Backend:")
    test("Marionette smoke test", test_marionette_smoke)

    print("\n📸 Screenshot:")
    test("take screenshot", test_screenshot)
    test("screen size", test_screen_size)

    print("\n🔧 Tool Execution:")
    test("execute ui_tree", test_execute_ui_tree)
    test("execute list_windows", test_execute_list_windows)
    test("execute find_element (no match)", test_execute_find_element_no_match)
    test("execute wait_for_element (timeout)", test_execute_wait_for_element_timeout)

    print("\n🔀 Perception Router:")
    test("perception routing", test_perception_routing)

    print("\n" + "=" * 60)
    total = PASS + FAIL + SKIP
    print(f"Results: {PASS}/{total} passed, {FAIL} failed, {SKIP} skipped")
    print("=" * 60)
    sys.exit(1 if FAIL > 0 else 0)
