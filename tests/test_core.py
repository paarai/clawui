#!/usr/bin/env python3
"""Core test suite for ClawUI - validates tool registration, backends, and basic operations."""

import os
import sys
import time
import tempfile
import io
from unittest.mock import patch

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
    from clawui.agent import create_tools
    tools = create_tools()
    assert len(tools) >= 45, f"Expected >=45 tools, got {len(tools)}"


def test_no_duplicate_tools():
    from clawui.agent import create_tools
    tools = create_tools()
    names = [t["name"] for t in tools]
    dupes = [n for n in set(names) if names.count(n) > 1]
    assert not dupes, f"Duplicate tools: {dupes}"


def test_all_tools_have_schema():
    from clawui.agent import create_tools
    tools = create_tools()
    for t in tools:
        assert "name" in t, f"Tool missing name: {t}"
        assert "description" in t, f"Tool {t['name']} missing description"
        assert "input_schema" in t, f"Tool {t['name']} missing input_schema"


def test_wait_for_element_registered():
    from clawui.agent import create_tools
    tools = create_tools()
    names = [t["name"] for t in tools]
    assert "wait_for_element" in names, "wait_for_element tool not registered"



# === Backend Imports ===
def test_atspi_import():
    from clawui.atspi_helper import list_applications, get_ui_tree_summary, find_elements


def test_x11_import():
    from clawui.x11_helper import list_windows


def test_cdp_discover_ports():
    """discover_cdp_ports should return a list of ints."""
    from clawui.cdp_helper import discover_cdp_ports
    result = discover_cdp_ports()
    assert isinstance(result, list)
    for p in result:
        assert isinstance(p, int)


def test_cdp_inherit_gui_env_from_ps_numeric_uid():
    """inherit_gui_session_env should parse ps output using numeric uid and import DISPLAY/XAUTHORITY."""
    from clawui import cdp_helper as mod

    original_display = os.environ.get("DISPLAY")
    original_xauthority = os.environ.get("XAUTHORITY")

    class _ProcResult:
        def __init__(self, stdout=""):
            self.stdout = stdout

    def fake_run(cmd, *args, **kwargs):
        if cmd[:3] == ['ps', '-eo', 'pid=,uid=,comm=']:
            return _ProcResult(stdout="111 1000 gnome-session\n")
        if cmd[:2] == ['loginctl', 'list-sessions']:
            return _ProcResult(stdout="")
        raise RuntimeError(f"Unexpected command: {cmd}")

    fake_env = b"DISPLAY=:99\x00XAUTHORITY=/tmp/.Xauthority-test\x00WAYLAND_DISPLAY=wayland-0\x00"

    def fake_exists(path):
        return path == '/proc/111/environ'

    real_open = open

    def fake_open(path, mode='r', *args, **kwargs):
        if path == '/proc/111/environ' and 'b' in mode:
            return io.BytesIO(fake_env)
        return real_open(path, mode, *args, **kwargs)

    try:
        os.environ.pop("DISPLAY", None)
        os.environ.pop("XAUTHORITY", None)

        with patch.object(mod.os, 'getuid', return_value=1000), \
             patch.object(mod.subprocess, 'run', side_effect=fake_run), \
             patch.object(mod.os.path, 'exists', side_effect=fake_exists), \
             patch('builtins.open', side_effect=fake_open):
            mod.inherit_gui_session_env()

        assert os.environ.get("DISPLAY") == ":99"
        assert os.environ.get("XAUTHORITY") == "/tmp/.Xauthority-test"
    finally:
        if original_display is None:
            os.environ.pop("DISPLAY", None)
        else:
            os.environ["DISPLAY"] = original_display

        if original_xauthority is None:
            os.environ.pop("XAUTHORITY", None)
        else:
            os.environ["XAUTHORITY"] = original_xauthority


def test_cdp_env_key_typo_fixed_wayland_socket_is_imported():
    """inherit_gui_session_env should import WAYLAND_SOCKET key (without leading-space typo)."""
    from clawui import cdp_helper as mod

    class _ProcResult:
        def __init__(self, stdout=""):
            self.stdout = stdout

    def fake_run(cmd, *args, **kwargs):
        if cmd[:3] == ['ps', '-eo', 'pid=,uid=,comm=']:
            return _ProcResult(stdout="222 1000 gnome-shell\n")
        if cmd[:2] == ['loginctl', 'list-sessions']:
            return _ProcResult(stdout="")
        raise RuntimeError(f"Unexpected command: {cmd}")

    fake_env = b"WAYLAND_SOCKET=socket-123\x00"

    def fake_exists(path):
        return path == '/proc/222/environ'

    real_open = open

    def fake_open(path, mode='r', *args, **kwargs):
        if path == '/proc/222/environ' and 'b' in mode:
            return io.BytesIO(fake_env)
        return real_open(path, mode, *args, **kwargs)

    original = os.environ.get("WAYLAND_SOCKET")
    original_display = os.environ.get("DISPLAY")
    original_xauthority = os.environ.get("XAUTHORITY")
    try:
        os.environ.pop("WAYLAND_SOCKET", None)
        os.environ.pop("DISPLAY", None)
        os.environ.pop("XAUTHORITY", None)
        with patch.object(mod.os, 'getuid', return_value=1000), \
             patch.object(mod.subprocess, 'run', side_effect=fake_run), \
             patch.object(mod.os.path, 'exists', side_effect=fake_exists), \
             patch('builtins.open', side_effect=fake_open):
            mod.inherit_gui_session_env()
        assert os.environ.get("WAYLAND_SOCKET") == "socket-123"
    finally:
        if original is None:
            os.environ.pop("WAYLAND_SOCKET", None)
        else:
            os.environ["WAYLAND_SOCKET"] = original

        if original_display is None:
            os.environ.pop("DISPLAY", None)
        else:
            os.environ["DISPLAY"] = original_display

        if original_xauthority is None:
            os.environ.pop("XAUTHORITY", None)
        else:
            os.environ["XAUTHORITY"] = original_xauthority


def test_cdp_import():
    from clawui.cdp_helper import CDPClient


def test_cdp_scroll_and_hover_methods_exist():
    """CDPClient should have scroll_page, hover, and hover_selector methods."""
    from clawui.cdp_helper import CDPClient
    c = CDPClient()
    assert hasattr(c, 'scroll_page'), "Missing scroll_page method"
    assert hasattr(c, 'hover'), "Missing hover method"
    assert hasattr(c, 'hover_selector'), "Missing hover_selector method"


def test_cdp_scroll_hover_tools_registered():
    """cdp_scroll and cdp_hover should be in the tool list."""
    from clawui.agent import create_tools
    tools = create_tools()
    names = [t["name"] for t in tools]
    assert "cdp_scroll" in names, "cdp_scroll tool not registered"
    assert "cdp_hover" in names, "cdp_hover tool not registered"


def test_cdp_wait_for_selector_result_parsing():
    """wait_for_selector should correctly parse Runtime.evaluate nested result.value payload."""
    from clawui.cdp_helper import CDPClient
    c = CDPClient()
    c.evaluate = lambda _expr: {"result": {"type": "object", "value": {"found": True, "text": "Submit", "tag": "BUTTON"}}}
    r = c.wait_for_selector("button", timeout=0.1, poll_interval=0.01)
    assert r.get("found") is True, f"Expected found=True, got {r}"
    assert r.get("text") == "Submit", f"Expected text='Submit', got {r}"


def test_cdp_wait_for_load_ready_state_nested_result():
    """CDPBackend.wait_for_load should handle nested Runtime.evaluate payloads."""
    from clawui.cdp_backend import CDPBackend

    backend = CDPBackend.__new__(CDPBackend)
    backend._ensure_connection = lambda: None

    class DummyClient:
        def evaluate(self, _expr):
            return {"result": {"value": "complete"}}

    backend.client = DummyClient()
    assert backend.wait_for_load(timeout=0.2, poll_interval=0.01) is True


def test_cdp_wait_for_load_timeout_returns_false():
    """CDPBackend.wait_for_load should return False on timeout when page never completes."""
    from clawui.cdp_backend import CDPBackend

    backend = CDPBackend.__new__(CDPBackend)
    backend._ensure_connection = lambda: None

    class DummyClient:
        def evaluate(self, _expr):
            return {"result": {"value": "loading"}}

    backend.client = DummyClient()
    assert backend.wait_for_load(timeout=0.05, poll_interval=0.01) is False


def test_marionette_import():
    from clawui.marionette_helper import MarionetteClient


def test_perception_import():
    from clawui.perception import list_applications, get_ui_tree_summary


def test_ocr_import():
    from clawui.ocr_tool import ocr_find_text


def test_recorder_import():
    from clawui.recorder import Recorder, Player


def test_export_recording_to_script():
    from clawui.recorder import export_to_script

    with tempfile.TemporaryDirectory() as td:
        recording_path = os.path.join(td, "demo.json")
        output_path = os.path.join(td, "demo.py")
        with open(recording_path, "w") as f:
            f.write(
                '{"metadata":{"count":2},"actions":[{"tool":"click","input":{"x":10,"y":20}},{"tool":"type_text","input":{"text":"hello"}}]}'
            )

        out = export_to_script(recording_path, output=output_path, delay=0.1)
        assert out == output_path
        assert os.path.exists(output_path), "Exported script does not exist"

        script = open(output_path, "r").read()
        assert "from clawui.actions import click" in script
        assert "click(10, 20)" in script
        assert "type_text('hello')" in script


# === AT-SPI Backend (requires desktop session) ===
def test_atspi_list_apps():
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        import pytest; pytest.skip("No display")
    from clawui.atspi_helper import list_applications
    apps = list_applications()
    # Should find at least something in a desktop session
    assert isinstance(apps, (list, str)), f"Unexpected type: {type(apps)}"


def test_atspi_ui_tree():
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        import pytest; pytest.skip("No display")
    from clawui.atspi_helper import get_ui_tree_summary
    tree = get_ui_tree_summary(max_depth=2)
    assert tree is not None, "UI tree returned None"



# === X11 Backend ===
def test_x11_list_windows():
    if not os.environ.get("DISPLAY"):
        import pytest; pytest.skip("No display")
    from clawui.x11_helper import list_windows
    windows = list_windows()
    assert isinstance(windows, list), f"Expected list, got {type(windows)}"



# === Screenshot ===
def test_screenshot():
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        import pytest; pytest.skip("No display")
    from clawui.screenshot import take_screenshot
    img = take_screenshot()
    assert img and len(img) > 100, "Screenshot too small or empty"


def test_screen_size():
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        import pytest; pytest.skip("No display")
    from clawui.screenshot import get_screen_size
    w, h = get_screen_size()
    assert w > 0 and h > 0, f"Invalid screen size: {w}x{h}"



# === Tool Execution (safe tools only) ===
def test_execute_ui_tree():
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        import pytest; pytest.skip("No display")
    from clawui.agent import execute_tool
    result = execute_tool("ui_tree", {})
    assert "type" in result, f"Missing 'type' in result: {result}"


def test_execute_list_windows():
    if not os.environ.get("DISPLAY"):
        import pytest; pytest.skip("No display")
    from clawui.agent import execute_tool
    result = execute_tool("list_windows", {})
    assert "type" in result, f"Missing 'type' in result: {result}"


def test_execute_find_element_no_match():
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        import pytest; pytest.skip("No display")
    from clawui.agent import execute_tool
    result = execute_tool("find_element", {"name": "__nonexistent_element_12345__"})
    assert "type" in result, f"Missing 'type' in result"


def test_execute_wait_for_element_timeout():
    """wait_for_element should timeout quickly for nonexistent element."""
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        import pytest; pytest.skip("No display")
    from clawui.agent import execute_tool
    start = time.time()
    result = execute_tool("wait_for_element", {"name_contains": "__nonexistent__", "timeout": 2})
    elapsed = time.time() - start
    assert "Timeout" in result.get("text", ""), f"Expected timeout, got: {result}"
    assert elapsed < 10, f"Took too long: {elapsed:.1f}s (expected ~2s timeout + AT-SPI overhead)"



# === Perception Router ===
def test_perception_routing():
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        import pytest; pytest.skip("No display")
    from clawui.perception import list_applications
    apps = list_applications()
    assert apps is not None, "Perception list_applications returned None"



# === Firefox Marionette Backend ===
def test_marionette_smoke():
    """Smoke test: connect to Firefox Marionette, navigate, get title."""
    # Only run if DISPLAY is available (requires GUI session)
    if not os.environ.get("DISPLAY"):
        import pytest; pytest.skip("No display")
    from clawui.marionette_helper import get_or_create_marionette_client
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
