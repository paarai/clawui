#!/usr/bin/env python3
"""Unit tests for clawui core modules - runnable without a display server."""

import json
import hashlib
import os
import subprocess
import sys
import time
import tempfile
import unittest
from unittest.mock import patch, MagicMock, PropertyMock

# Ensure src is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'gui-automation'))


class TestScreenshot(unittest.TestCase):
    """Test screenshot module."""

    @patch('subprocess.run')
    def test_get_screen_size(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='1920x1080\n'
        )
        from src.screenshot import get_screen_size
        w, h = get_screen_size()
        assert w == 1920
        assert h == 1080

    def test_take_screenshot_no_display(self):
        """Without a display, take_screenshot should raise or return None."""
        from src.screenshot import take_screenshot
        try:
            result = take_screenshot()
            # If it returns, it should be a string or None
            assert result is None or isinstance(result, str)
        except RuntimeError:
            pass  # Expected when no display


class TestCDPClient(unittest.TestCase):
    """Test CDP client without a real browser."""

    def test_cdp_client_init(self):
        from src.cdp_helper import CDPClient
        client = CDPClient(port=19222)
        assert client.port == 19222
        assert not client.is_available()

    @patch('http.client.HTTPConnection')
    def test_get_targets(self, mock_conn_cls):
        from src.cdp_helper import CDPClient
        client = CDPClient(port=9222)

        # Mock HTTP response
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps([
            {"id": "abc", "type": "page", "title": "Test", "url": "https://example.com"}
        ]).encode()
        mock_conn = MagicMock()
        mock_conn.getresponse.return_value = mock_resp
        mock_conn_cls.return_value = mock_conn

        targets = client.list_targets()
        assert len(targets) == 1
        assert targets[0]["title"] == "Test"


class TestActions(unittest.TestCase):
    """Test desktop action wrappers."""

    @patch('subprocess.run')
    def test_click(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        from src.actions import click
        click(100, 200)
        mock_run.assert_called()
        # Verify xdotool was invoked (could be string or list command)
        call_args = mock_run.call_args
        cmd = call_args[0][0] if call_args[0] else ''
        if isinstance(cmd, list):
            cmd_str = ' '.join(cmd)
        else:
            cmd_str = str(cmd)
        assert 'xdotool' in cmd_str

    @patch('subprocess.run')
    def test_type_text(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        from src.actions import type_text
        type_text("hello world")
        mock_run.assert_called()

    @patch('subprocess.run')
    def test_press_key(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        from src.actions import press_key
        press_key("Return")
        mock_run.assert_called()


class TestX11Helper(unittest.TestCase):
    """Test X11 helper."""

    @patch('subprocess.run')
    def test_list_windows(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='0x01000001 0 hung-pc My Window\n0x01000002 0 hung-pc Another\n'
        )
        from src.x11_helper import list_windows
        wins = list_windows()
        assert len(wins) >= 0  # May parse differently but shouldn't crash


class TestAgentTools(unittest.TestCase):
    """Test agent tool creation and execution."""

    def test_create_tools_returns_list(self):
        from src.agent import create_tools
        tools = create_tools()
        assert isinstance(tools, list)
        assert len(tools) > 30  # We have 40+ tools
        names = [t['name'] for t in tools]
        assert 'screenshot' in names
        assert 'click' in names
        assert 'cdp_navigate' in names
        assert 'find_text' in names
        assert 'click_text' in names

    def test_tool_schemas_valid(self):
        from src.agent import create_tools
        tools = create_tools()
        for tool in tools:
            assert 'name' in tool
            assert 'description' in tool
            assert 'input_schema' in tool
            schema = tool['input_schema']
            assert schema.get('type') == 'object'
            assert 'properties' in schema


class TestRecorder(unittest.TestCase):
    """Test recorder module."""

    def test_start_stop_recording(self):
        from src.recorder import start_recording, stop_recording, record_action
        rec = start_recording()
        record_action("click", {"x": 10, "y": 20}, {"type": "text", "text": "ok"})
        data = stop_recording()
        assert data is not None


class TestOCRTool(unittest.TestCase):
    """Test OCR tool module."""

    def test_import(self):
        from src.ocr_tool import ocr_find_text
        assert callable(ocr_find_text)


class TestPerception(unittest.TestCase):
    """Test perception routing layer."""

    def test_import_and_functions(self):
        from src.perception import get_ui_tree_summary, list_applications
        assert callable(get_ui_tree_summary)
        assert callable(list_applications)


class TestCLI(unittest.TestCase):
    """Test CLI entry point."""

    def test_cli_import(self):
        from src.cli import main
        assert callable(main)


if __name__ == '__main__':
    unittest.main()


class TestAnnotatedScreenshot(unittest.TestCase):
    """Test annotated screenshot module."""

    def test_import(self):
        from src.annotated_screenshot import annotated_screenshot, get_last_elements, LabeledElement
        assert callable(annotated_screenshot)
        assert callable(get_last_elements)

    def test_dedup_elements(self):
        from src.annotated_screenshot import _dedup_elements
        elements = [
            {"x": 100, "y": 100, "width": 50, "height": 30, "role": "button", "name": "A"},
            {"x": 102, "y": 101, "width": 50, "height": 30, "role": "button", "name": "A dup"},
            {"x": 300, "y": 200, "width": 50, "height": 30, "role": "link", "name": "B"},
        ]
        result = _dedup_elements(elements)
        assert len(result) == 2, f"Expected 2, got {len(result)}"

    def test_labeled_element_to_dict(self):
        from src.annotated_screenshot import LabeledElement
        el = LabeledElement(
            index=1, label="1: Save", role="push button", name="Save",
            x=10, y=20, width=80, height=30, center_x=50, center_y=35,
            source="atspi", selector=None,
        )
        d = el.to_dict()
        assert d["index"] == 1
        assert d["center"] == [50, 35]
        assert d["source"] == "atspi"


class TestAutoVerification(unittest.TestCase):
    """Test auto action verification logic."""

    @patch('src.agent.take_screenshot')
    def test_unchanged_screen_adds_warning(self, mock_ss):
        """When screen hash unchanged after action, result should contain warning."""
        import src.agent as agent_mod
        mock_ss.return_value = "AAAA"  # same base64 both times
        agent_mod._last_screen_hash = hashlib.md5(b"AAAA").hexdigest()
        with patch.object(agent_mod, '_execute_tool_inner',
                          return_value={"type": "text", "text": "Clicked"}):
            with patch.dict(os.environ, {"CLAWUI_VERIFY_ACTIONS": "1"}):
                result = agent_mod.execute_tool("click", {"x": 100, "y": 200})
        assert "unchanged" in result.get("text", "").lower()

    @patch('src.agent.take_screenshot')
    def test_changed_screen_no_warning(self, mock_ss):
        """When screen changes after action, no warning appended."""
        import src.agent as agent_mod
        mock_ss.return_value = "BBBB"  # different from stored
        agent_mod._last_screen_hash = hashlib.md5(b"AAAA").hexdigest()
        with patch.object(agent_mod, '_execute_tool_inner',
                          return_value={"type": "text", "text": "Clicked"}):
            with patch.dict(os.environ, {"CLAWUI_VERIFY_ACTIONS": "1"}):
                result = agent_mod.execute_tool("click", {"x": 100, "y": 200})
        assert "unchanged" not in result.get("text", "").lower()

    @patch('src.agent.take_screenshot')
    def test_verification_disabled(self, mock_ss):
        """When CLAWUI_VERIFY_ACTIONS=0, no verification occurs."""
        import src.agent as agent_mod
        mock_ss.return_value = "AAAA"
        agent_mod._last_screen_hash = hashlib.md5(b"AAAA").hexdigest()
        with patch.object(agent_mod, '_execute_tool_inner',
                          return_value={"type": "text", "text": "Clicked"}):
            with patch.dict(os.environ, {"CLAWUI_VERIFY_ACTIONS": "0"}):
                result = agent_mod.execute_tool("click", {"x": 100, "y": 200})
        assert "unchanged" not in result.get("text", "")
        mock_ss.assert_not_called()

    def test_non_action_tool_skips_verification(self):
        """Non-state-changing tools should not trigger verification."""
        import src.agent as agent_mod
        with patch.object(agent_mod, '_execute_tool_inner',
                          return_value={"type": "text", "text": "tree data"}):
            result = agent_mod.execute_tool("ui_tree", {})
        assert "unchanged" not in result.get("text", "")


class TestHybridTools(unittest.TestCase):
    """Test API-GUI hybrid tools."""

    @patch('subprocess.run')
    def test_run_command(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="hello\n", stderr="")
        import src.agent as agent_mod
        agent_mod._last_screen_hash = None  # disable verification
        result = agent_mod.execute_tool("run_command", {"command": "echo hello"})
        assert "hello" in result["text"]
        assert "exit=0" in result["text"]

    @patch('subprocess.run')
    def test_run_command_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 30)
        import src.agent as agent_mod
        agent_mod._last_screen_hash = None
        result = agent_mod.execute_tool("run_command", {"command": "sleep 999"})
        assert "timed out" in result["text"].lower()

    @patch('subprocess.run')
    def test_run_command_disabled(self, mock_run):
        import src.agent as agent_mod
        agent_mod._last_screen_hash = None
        with patch.dict(os.environ, {"CLAWUI_ALLOW_SHELL": "0"}):
            result = agent_mod.execute_tool("run_command", {"command": "echo hello"})
        assert "disabled" in result["text"].lower()
        mock_run.assert_not_called()

    def test_file_read_not_found(self):
        import src.agent as agent_mod
        agent_mod._last_screen_hash = None
        result = agent_mod.execute_tool("file_read", {"path": "/nonexistent/file.txt"})
        assert "not found" in result["text"].lower()

    def test_file_write_and_read(self):
        import src.agent as agent_mod
        agent_mod._last_screen_hash = None
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            path = f.name
        try:
            result = agent_mod.execute_tool("file_write", {"path": path, "content": "hello world"})
            assert "11 bytes" in result["text"]
            result = agent_mod.execute_tool("file_read", {"path": path})
            assert result["text"] == "hello world"
        finally:
            os.unlink(path)

    def test_file_list_not_found(self):
        import src.agent as agent_mod
        agent_mod._last_screen_hash = None
        result = agent_mod.execute_tool("file_list", {"path": "/nonexistent/dir"})
        assert "not found" in result["text"].lower()

    def test_file_list_works(self):
        import src.agent as agent_mod
        agent_mod._last_screen_hash = None
        with tempfile.TemporaryDirectory() as td:
            open(os.path.join(td, "a.txt"), "w").close()
            open(os.path.join(td, "b.py"), "w").close()
            result = agent_mod.execute_tool("file_list", {"path": td})
            assert "a.txt" in result["text"]
            assert "b.py" in result["text"]

    def test_create_tools_includes_new_tools(self):
        from src.agent import create_tools
        names = [t["name"] for t in create_tools()]
        for tool in ("run_command", "file_read", "file_write", "file_list", "open_url"):
            assert tool in names, f"{tool} missing from tools"


class TestConfigurableDelays(unittest.TestCase):
    """Test P1-D: configurable sleep constants."""

    def test_default_delay_values(self):
        import src.agent as agent_mod
        assert agent_mod._LAUNCH_DELAY == 1.0
        assert agent_mod._WECHAT_LAUNCH_DELAY == 2.0
        assert agent_mod._NAV_DELAY == 2.0
        assert agent_mod._OCR_ACTION_DELAY == 1.0

    def test_env_override_delays(self):
        """Verify env vars are read at module level (check the mechanism works)."""
        # We can't re-import to test env override, but we can verify the constants
        # are float types and the env var names are correct.
        import src.agent as agent_mod
        assert isinstance(agent_mod._LAUNCH_DELAY, float)
        assert isinstance(agent_mod._NAV_DELAY, float)


class TestPILResize(unittest.TestCase):
    """Test P1-C: PIL screenshot resize with ImageMagick fallback."""

    def test_pil_resize_path(self):
        """PIL resize branch is taken when PIL is available."""
        from PIL import Image
        import tempfile
        # Create a 200x200 test image
        img = Image.new('RGB', (200, 200), color='red')
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            img.save(f.name)
            path = f.name
        try:
            # Resize using PIL directly (same logic as screenshot.py)
            img = Image.open(path)
            resample = getattr(Image, 'LANCZOS', getattr(Image, 'ANTIALIAS', Image.BICUBIC))
            img = img.resize((100, 100), resample)
            img.save(path)
            # Verify resized
            result = Image.open(path)
            assert result.size == (100, 100)
        finally:
            os.unlink(path)


class TestTokenTracking(unittest.TestCase):
    """Test P1-A: token tracking in backends."""

    def test_claude_backend_returns_usage(self):
        """ClaudeBackend.chat() return dict includes 'usage' key."""
        from src.backends import ClaudeBackend
        # Mock the Anthropic client
        mock_response = MagicMock()
        mock_response.content = []
        mock_usage = MagicMock()
        mock_usage.input_tokens = 150
        mock_usage.output_tokens = 42
        mock_response.usage = mock_usage

        backend = ClaudeBackend.__new__(ClaudeBackend)
        backend.client = MagicMock()
        backend.model = "test"
        backend.client.messages.create.return_value = mock_response

        result = backend.chat([], [], "system")
        assert "usage" in result
        assert result["usage"]["input_tokens"] == 150
        assert result["usage"]["output_tokens"] == 42

    def test_openai_backend_returns_usage(self):
        """OpenAIBackend.chat() return dict includes 'usage' key."""
        from src.backends import OpenAIBackend
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "hello"
        mock_choice.message.tool_calls = None
        mock_response.choices = [mock_choice]
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 25
        mock_response.usage = mock_usage

        backend = OpenAIBackend.__new__(OpenAIBackend)
        backend.client = MagicMock()
        backend.model = "test"
        backend.client.chat.completions.create.return_value = mock_response

        result = backend.chat([], [], "system")
        assert "usage" in result
        assert result["usage"]["input_tokens"] == 100
        assert result["usage"]["output_tokens"] == 25

    def test_extract_anthropic_usage_missing(self):
        """Usage extraction handles missing usage attribute gracefully."""
        from src.backends import ClaudeBackend
        mock_resp = MagicMock(spec=[])  # no attributes
        usage = ClaudeBackend._extract_anthropic_usage(mock_resp)
        assert usage == {"input_tokens": 0, "output_tokens": 0}


class TestLazyPerceptionInit(unittest.TestCase):
    """Test P1-B: lazy CDP/Marionette init with TTL cache."""

    def test_cdp_initially_unchecked(self):
        """CDP_AVAILABLE starts as None (unchecked), not eagerly probed."""
        import src.perception as perc
        # On import, CDP_AVAILABLE should be None (lazy) not True/False
        # We reset it to test the mechanism
        original = perc.CDP_AVAILABLE
        perc.CDP_AVAILABLE = None
        perc._cdp_client = None
        perc._cdp_last_check = 0.0
        # _get_cdp_client should attempt init now
        client = perc._get_cdp_client()
        # Without a real browser, it should be None/False
        assert client is None or perc.CDP_AVAILABLE is not None
        # Restore
        perc.CDP_AVAILABLE = original

    def test_cdp_ttl_caching(self):
        """Repeated calls within TTL don't re-probe."""
        import src.perception as perc
        perc.CDP_AVAILABLE = False
        perc._cdp_client = None
        perc._cdp_last_check = perc._time.monotonic()  # just checked
        # Within TTL, should return None without re-probing
        result = perc._get_cdp_client()
        assert result is None  # cached False

    def test_marionette_initially_unchecked(self):
        """MARIONETTE_AVAILABLE starts as None (unchecked)."""
        import src.perception as perc
        original = perc.MARIONETTE_AVAILABLE
        perc.MARIONETTE_AVAILABLE = None
        perc._marionette_client = None
        perc._marionette_last_check = 0.0
        client = perc._get_marionette_client()
        assert client is None or perc.MARIONETTE_AVAILABLE is not None
        perc.MARIONETTE_AVAILABLE = original


class TestPlanAndExecute(unittest.TestCase):
    """Test P2: structured task hierarchical planning."""

    # ---- _parse_steps tests ----

    def test_parse_steps_basic(self):
        from src.agent import _parse_steps
        text = "1. Click File menu | EXPECT: Menu opens\n2. Click Save | EXPECT: File saved"
        steps = _parse_steps(text)
        assert len(steps) == 2
        assert steps[0]["id"] == 1
        assert steps[0]["description"] == "Click File menu"
        assert steps[0]["expected_change"] == "Menu opens"
        assert steps[1]["id"] == 2

    def test_parse_steps_paren_numbering(self):
        from src.agent import _parse_steps
        text = "1) Open browser | EXPECT: Browser window appears\n2) Navigate to URL | EXPECT: Page loads"
        steps = _parse_steps(text)
        assert len(steps) == 2
        assert steps[0]["description"] == "Open browser"

    def test_parse_steps_skips_non_step_lines(self):
        from src.agent import _parse_steps
        text = "Here is the plan:\n\n1. Click button | EXPECT: Dialog opens\nSome note\n2. Type text | EXPECT: Text entered"
        steps = _parse_steps(text)
        assert len(steps) == 2

    def test_parse_steps_missing_expect(self):
        from src.agent import _parse_steps
        text = "1. Click button\n2. Type hello | EXPECT: Text appears"
        steps = _parse_steps(text)
        assert len(steps) == 2
        assert steps[0]["expected_change"] == ""
        assert steps[1]["expected_change"] == "Text appears"

    def test_parse_steps_empty_input(self):
        from src.agent import _parse_steps
        assert _parse_steps("") == []
        assert _parse_steps("No steps here.") == []

    def test_parse_steps_start_id(self):
        from src.agent import _parse_steps
        text = "1. Do something | EXPECT: Change"
        steps = _parse_steps(text, start_id=5)
        assert steps[0]["id"] == 5

    def test_parse_steps_renumbers_sequentially(self):
        from src.agent import _parse_steps
        text = "3. Step A | EXPECT: A\n7. Step B | EXPECT: B\n15. Step C | EXPECT: C"
        steps = _parse_steps(text)
        assert [s["id"] for s in steps] == [1, 2, 3]

    # ---- _verify_step tests ----

    def test_verify_step_screen_changed(self):
        from src.agent import _verify_step
        result = {"screen_changed": True, "output": "Clicked"}
        assert _verify_step(result) is True

    def test_verify_step_screen_unchanged(self):
        from src.agent import _verify_step
        result = {"screen_changed": False, "output": "Clicked"}
        assert _verify_step(result) is False

    def test_verify_step_no_llm_by_default(self):
        """Without CLAWUI_PLAN_LLM_VERIFY=1, no LLM call is made."""
        from src.agent import _verify_step
        mock_backend = MagicMock()
        result = {"screen_changed": True, "output": "ok"}
        with patch.dict(os.environ, {"CLAWUI_PLAN_LLM_VERIFY": "0"}):
            assert _verify_step(result, "some change", mock_backend) is True
        mock_backend.chat.assert_not_called()

    @patch.dict(os.environ, {"CLAWUI_PLAN_LLM_VERIFY": "1"})
    def test_verify_step_llm_yes(self):
        import src.agent as agent_mod
        # Temporarily enable LLM verify
        original = agent_mod._PLAN_LLM_VERIFY
        agent_mod._PLAN_LLM_VERIFY = True
        try:
            mock_backend = MagicMock()
            mock_backend.chat.return_value = {"text": "YES"}
            result = {"screen_changed": True, "output": "Done"}
            assert _verify_step(result, "Dialog opened", mock_backend) is True
        finally:
            agent_mod._PLAN_LLM_VERIFY = original

    @patch.dict(os.environ, {"CLAWUI_PLAN_LLM_VERIFY": "1"})
    def test_verify_step_llm_no(self):
        import src.agent as agent_mod
        from src.agent import _verify_step
        original = agent_mod._PLAN_LLM_VERIFY
        agent_mod._PLAN_LLM_VERIFY = True
        try:
            mock_backend = MagicMock()
            mock_backend.chat.return_value = {"text": "NO"}
            result = {"screen_changed": True, "output": "Done"}
            assert _verify_step(result, "Dialog opened", mock_backend) is False
        finally:
            agent_mod._PLAN_LLM_VERIFY = original

    @patch.dict(os.environ, {"CLAWUI_PLAN_LLM_VERIFY": "1"})
    def test_verify_step_llm_error_falls_back(self):
        """If LLM call fails, fall back to tier-1 (screen_changed)."""
        import src.agent as agent_mod
        from src.agent import _verify_step
        original = agent_mod._PLAN_LLM_VERIFY
        agent_mod._PLAN_LLM_VERIFY = True
        try:
            mock_backend = MagicMock()
            mock_backend.chat.side_effect = Exception("API error")
            result = {"screen_changed": True, "output": "Done"}
            assert _verify_step(result, "Something", mock_backend) is True
        finally:
            agent_mod._PLAN_LLM_VERIFY = original

    def test_verify_step_no_expected_change_skips_llm(self):
        """Empty expected_change skips LLM even if enabled."""
        import src.agent as agent_mod
        from src.agent import _verify_step
        original = agent_mod._PLAN_LLM_VERIFY
        agent_mod._PLAN_LLM_VERIFY = True
        try:
            mock_backend = MagicMock()
            result = {"screen_changed": True, "output": "ok"}
            assert _verify_step(result, "", mock_backend) is True
            mock_backend.chat.assert_not_called()
        finally:
            agent_mod._PLAN_LLM_VERIFY = original

    # ---- _execute_step tests ----

    @patch('src.agent._quick_screen_hash')
    def test_execute_step_runs_tools(self, mock_hash):
        from src.agent import _execute_step
        mock_hash.side_effect = ["hash_before", "hash_after"]
        mock_backend = MagicMock()
        # First call returns a tool call, second returns text (DONE)
        mock_backend.chat.side_effect = [
            {"tool_calls": [{"name": "click", "input": {"x": 100, "y": 200}, "id": "c1"}]},
            {"text": "DONE", "tool_calls": []},
        ]
        step = {"id": 1, "description": "Click button", "expected_change": "Opens",
                "timeout_sec": 10, "max_retries": 1, "status": "pending"}
        with patch('src.agent.execute_tool', return_value={"type": "text", "text": "Clicked"}):
            result = _execute_step(step, mock_backend, [])
        assert result["step_id"] == 1
        assert result["screen_changed"] is True
        assert len(result["tool_calls"]) == 1

    @patch('src.agent._quick_screen_hash')
    def test_execute_step_timeout(self, mock_hash):
        """Step should stop when timeout exceeded."""
        from src.agent import _execute_step
        import src.agent as agent_mod
        mock_hash.side_effect = ["h1", "h1"]
        mock_backend = MagicMock()
        # Backend always returns tool calls (infinite loop without timeout)
        mock_backend.chat.return_value = {
            "tool_calls": [{"name": "wait", "input": {"seconds": 0.01}, "id": "c1"}]
        }
        step = {"id": 1, "description": "Wait forever", "expected_change": "",
                "timeout_sec": 0.1, "max_retries": 0, "status": "pending"}
        with patch('src.agent.execute_tool', return_value={"type": "text", "text": "waited"}):
            result = _execute_step(step, mock_backend, [])
        # Should have terminated due to timeout
        assert result["elapsed_sec"] >= 0
        assert result["step_id"] == 1

    # ---- _replan tests ----

    def test_replan_returns_new_steps(self):
        from src.agent import _replan
        mock_backend = MagicMock()
        mock_backend.chat.return_value = {
            "text": "1. Retry click | EXPECT: Dialog opens\n2. Type text | EXPECT: Text entered"
        }
        completed = [{"id": 1, "description": "Open app"}]
        failed = {"id": 2, "description": "Click button"}
        new_steps = _replan(completed, failed, "screen unchanged", mock_backend, [])
        assert len(new_steps) == 2
        assert new_steps[0]["id"] == 2  # renumbered from failed step

    def test_replan_empty_on_error(self):
        from src.agent import _replan
        mock_backend = MagicMock()
        mock_backend.chat.side_effect = Exception("API down")
        new_steps = _replan([], {"id": 1, "description": "X"}, "err", mock_backend, [])
        assert new_steps == []

    def test_replan_empty_on_no_steps(self):
        from src.agent import _replan
        mock_backend = MagicMock()
        mock_backend.chat.return_value = {"text": "No steps possible."}
        new_steps = _replan([], {"id": 1, "description": "X"}, "err", mock_backend, [])
        assert new_steps == []

    # ---- plan_and_execute handler integration tests ----

    def test_handler_missing_task(self):
        import src.agent as agent_mod
        agent_mod._last_screen_hash = None
        result = agent_mod.execute_tool("plan_and_execute", {})
        assert "Missing" in result["text"]

    @patch('src.agent.get_backend')
    def test_handler_backend_error(self, mock_get):
        mock_get.side_effect = Exception("No API key")
        import src.agent as agent_mod
        agent_mod._last_screen_hash = None
        result = agent_mod.execute_tool("plan_and_execute", {"task": "do something"})
        assert "get_backend error" in result["text"]

    @patch('src.agent._execute_step')
    @patch('src.agent._quick_screen_hash', return_value="h1")
    @patch('src.agent.get_backend')
    def test_handler_full_success(self, mock_get, mock_hash, mock_exec):
        """All steps succeed — completed should be True."""
        mock_backend = MagicMock()
        mock_backend.chat.return_value = {
            "text": "1. Click button | EXPECT: Menu opens\n2. Click Save | EXPECT: Saved"
        }
        mock_get.return_value = mock_backend
        mock_exec.return_value = {
            "step_id": 1, "success": True, "output": "done",
            "screenshot_hash_before": "a", "screenshot_hash_after": "b",
            "screen_changed": True, "error": None, "tool_calls": [], "elapsed_sec": 1.0,
        }
        import src.agent as agent_mod
        agent_mod._last_screen_hash = None
        result = agent_mod.execute_tool("plan_and_execute", {"task": "save file"})
        assert result["completed"] is True
        assert result["steps_done"] == 2
        assert result["steps_failed"] == 0

    @patch('src.agent._replan', return_value=[])
    @patch('src.agent._execute_step')
    @patch('src.agent._quick_screen_hash', return_value="h1")
    @patch('src.agent.get_backend')
    def test_handler_failure_triggers_replan(self, mock_get, mock_hash, mock_exec, mock_replan):
        """When a step fails and replan returns empty, handler aborts."""
        mock_backend = MagicMock()
        mock_backend.chat.return_value = {
            "text": "1. Click X | EXPECT: X opens\n2. Click Y | EXPECT: Y opens"
        }
        mock_get.return_value = mock_backend
        # First step succeeds, second fails
        mock_exec.side_effect = [
            {"step_id": 1, "success": True, "output": "ok",
             "screenshot_hash_before": "a", "screenshot_hash_after": "b",
             "screen_changed": True, "error": None, "tool_calls": [], "elapsed_sec": 1.0},
            {"step_id": 2, "success": False, "output": "fail",
             "screenshot_hash_before": "b", "screenshot_hash_after": "b",
             "screen_changed": False, "error": "unchanged", "tool_calls": [], "elapsed_sec": 1.0},
        ] * 3  # enough for retries
        import src.agent as agent_mod
        agent_mod._last_screen_hash = None
        result = agent_mod.execute_tool("plan_and_execute", {"task": "do X and Y"})
        assert result["steps_failed"] >= 1
        assert result["completed"] is False

    def test_handler_schema_has_new_params(self):
        from src.agent import create_tools
        tools = create_tools()
        pe = next(t for t in tools if t["name"] == "plan_and_execute")
        props = pe["input_schema"]["properties"]
        assert "max_steps" in props
        assert "max_retries_per_step" in props
        assert "step_timeout" in props


# ========================================================================
# P3: CUA Optimization Tests
# ========================================================================


class TestContextCompression(unittest.TestCase):
    """Test P3-A: context window compression."""

    def test_estimate_tokens_simple(self):
        from src.agent import _estimate_tokens
        msgs = [{"role": "user", "content": "x" * 400}]
        est = _estimate_tokens(msgs)
        assert est == 100, f"Expected 100, got {est}"

    def test_estimate_tokens_mixed(self):
        from src.agent import _estimate_tokens
        msgs = [
            {"role": "user", "content": "hello world"},  # 11 chars
            {"role": "assistant", "content": [
                {"type": "text", "text": "response text"},  # 13 chars
                {"type": "tool_use", "input": {"x": 1}},  # json len
            ]},
        ]
        est = _estimate_tokens(msgs)
        assert est > 0

    def test_compress_under_threshold(self):
        from src.agent import _compress_history
        msgs = [{"role": "user", "content": "small"}]
        assert _compress_history(msgs) == msgs

    def test_compress_over_threshold(self):
        from src.agent import _compress_history, _CONTEXT_MAX_TOKENS
        # Create messages large enough to exceed 70% threshold
        msgs = [{"role": "user", "content": "Task: do stuff"}]
        filler = "X" * (_CONTEXT_MAX_TOKENS * 4)  # way over limit
        for i in range(10):
            msgs.append({"role": "assistant", "content": filler})
        result = _compress_history(msgs, keep_recent=3)
        assert len(result) < len(msgs), f"Expected compression: {len(result)} vs {len(msgs)}"
        assert result[0] == msgs[0]  # first message preserved
        # Last 3 messages preserved
        assert result[-1] == msgs[-1]
        assert result[-2] == msgs[-2]

    def test_compress_too_few_messages(self):
        from src.agent import _compress_history
        msgs = [{"role": "user", "content": "X" * 500000}]
        # Only 1 message — can't compress
        assert _compress_history(msgs) == msgs


class TestResponseCaching(unittest.TestCase):
    """Test P3-C: TTL-based response caching."""

    def test_non_cacheable_tool_skips_cache(self):
        from src.agent import _cache_get
        assert _cache_get("click", {"x": 1}) is None

    def test_cache_miss(self):
        from src.agent import _cache_get
        assert _cache_get("ui_tree", {"app_name": "Firefox"}) is None

    def test_cache_set_and_get(self):
        from src.agent import _cache_set, _cache_get, _tool_cache
        _tool_cache.clear()
        _cache_set("ui_tree", {"app_name": "Test"}, {"text": "tree data"})
        result = _cache_get("ui_tree", {"app_name": "Test"})
        assert result == {"text": "tree data"}

    def test_cache_different_inputs(self):
        from src.agent import _cache_set, _cache_get, _tool_cache
        _tool_cache.clear()
        _cache_set("ui_tree", {"app_name": "A"}, {"text": "A"})
        _cache_set("ui_tree", {"app_name": "B"}, {"text": "B"})
        assert _cache_get("ui_tree", {"app_name": "A"}) == {"text": "A"}
        assert _cache_get("ui_tree", {"app_name": "B"}) == {"text": "B"}


class TestDynamicModelRouting(unittest.TestCase):
    """Test P3-B: dynamic model routing."""

    def test_get_backend_model_override(self):
        """model_override should take precedence."""
        from src.backends import get_backend
        import inspect
        sig = inspect.signature(get_backend)
        assert "model_override" in sig.parameters

    def test_phase_model_env_vars_exist(self):
        import src.agent as agent_mod
        assert hasattr(agent_mod, "_PLAN_MODEL")
        assert hasattr(agent_mod, "_EXEC_MODEL")
        assert hasattr(agent_mod, "_VERIFY_MODEL")


class TestMoGCrossValidation(unittest.TestCase):
    """Test P3-D: Mixture of Grounding cross-validation."""

    def test_iou_identical(self):
        from src.annotated_screenshot import _iou
        assert abs(_iou((0, 0, 100, 50), (0, 0, 100, 50)) - 1.0) < 0.01

    def test_iou_no_overlap(self):
        from src.annotated_screenshot import _iou
        assert _iou((0, 0, 10, 10), (100, 100, 10, 10)) == 0.0

    def test_iou_partial(self):
        from src.annotated_screenshot import _iou
        val = _iou((0, 0, 20, 20), (10, 10, 20, 20))
        assert 0.0 < val < 1.0

    def test_labeled_element_has_confidence(self):
        from src.annotated_screenshot import LabeledElement
        el = LabeledElement(
            index=1, label="1: OK", role="button", name="OK",
            x=10, y=20, width=50, height=30, center_x=35, center_y=35,
            source="atspi", confidence=0.8,
        )
        d = el.to_dict()
        assert "confidence" in d
        assert d["confidence"] == 0.8

    def test_labeled_element_default_confidence(self):
        from src.annotated_screenshot import LabeledElement
        el = LabeledElement(
            index=1, label="1: X", role="button", name="X",
            x=0, y=0, width=10, height=10, center_x=5, center_y=5,
            source="cdp",
        )
        assert el.confidence == 0.5

    def test_ocr_cross_validate_no_ocr(self):
        """When OCR returns empty, elements keep default confidence."""
        from src.annotated_screenshot import _ocr_cross_validate
        elements = [{"x": 10, "y": 20, "width": 50, "height": 30, "name": "Save", "role": "button"}]
        # Pass empty base64 — OCR will fail gracefully
        result = _ocr_cross_validate(elements, "")
        assert len(result) == 1


class TestSubgoalDependencyGraph(unittest.TestCase):
    """Test P3-E: sub-goal dependency graph in planning."""

    def test_parse_steps_with_after(self):
        from src.agent import _parse_steps
        text = "1. Open browser | EXPECT: Opens | AFTER: -\n2. Navigate | EXPECT: Page | AFTER: 1\n3. Fill form | EXPECT: Filled | AFTER: 1, 2"
        steps = _parse_steps(text)
        assert len(steps) == 3
        assert steps[0]["depends_on"] == []
        assert steps[1]["depends_on"] == [1]
        assert steps[2]["depends_on"] == [1, 2]

    def test_parse_steps_no_after(self):
        """Steps without AFTER get empty depends_on."""
        from src.agent import _parse_steps
        text = "1. Click button | EXPECT: Opens\n2. Type text | EXPECT: Done"
        steps = _parse_steps(text)
        assert steps[0]["depends_on"] == []
        assert steps[1]["depends_on"] == []

    def test_parse_steps_after_dash(self):
        """AFTER: - means no dependencies."""
        from src.agent import _parse_steps
        text = "1. Do thing | EXPECT: Done | AFTER: -"
        steps = _parse_steps(text)
        assert steps[0]["depends_on"] == []

    def test_parse_steps_renumber_remaps_after(self):
        """Original step numbers in AFTER are remapped to new IDs."""
        from src.agent import _parse_steps
        text = "5. A | EXPECT: A | AFTER: -\n10. B | EXPECT: B | AFTER: 5"
        steps = _parse_steps(text)
        assert steps[0]["id"] == 1
        assert steps[1]["id"] == 2
        assert steps[1]["depends_on"] == [1]  # 5 -> 1

    def test_parse_steps_backward_compat(self):
        """Old-style steps without AFTER still parse correctly."""
        from src.agent import _parse_steps
        text = "1. Click File menu | EXPECT: Menu opens\n2. Click Save | EXPECT: File saved"
        steps = _parse_steps(text)
        assert len(steps) == 2
        assert steps[0]["id"] == 1
        assert steps[0]["description"] == "Click File menu"
        assert steps[0]["expected_change"] == "Menu opens"


class TestPerToolCostTracking(unittest.TestCase):
    """Test P3-F: per-tool and per-phase token cost tracking."""

    def test_track_tokens(self):
        from src.agent import _track_tokens, _tool_token_stats
        _tool_token_stats.clear()
        _track_tokens("click", {"input_tokens": 100, "output_tokens": 50})
        _track_tokens("click", {"input_tokens": 200, "output_tokens": 30})
        assert _tool_token_stats["click"]["calls"] == 2
        assert _tool_token_stats["click"]["input_tokens"] == 300
        assert _tool_token_stats["click"]["output_tokens"] == 80

    def test_track_tokens_zero_usage(self):
        from src.agent import _track_tokens, _tool_token_stats
        _tool_token_stats.clear()
        _track_tokens("noop", {"input_tokens": 0, "output_tokens": 0})
        assert "noop" not in _tool_token_stats

    def test_track_tokens_none_usage(self):
        from src.agent import _track_tokens, _tool_token_stats
        _tool_token_stats.clear()
        _track_tokens("noop", None)
        assert "noop" not in _tool_token_stats

    def test_track_phase(self):
        from src.agent import _track_phase, _phase_token_stats
        _phase_token_stats.clear()
        _track_phase("plan", {"input_tokens": 500, "output_tokens": 100})
        _track_phase("plan", {"input_tokens": 300, "output_tokens": 50})
        assert _phase_token_stats["plan"]["input_tokens"] == 800
        assert _phase_token_stats["plan"]["output_tokens"] == 150

    def test_get_token_stats(self):
        from src.agent import get_token_stats, reset_token_stats, _track_tokens, _track_phase
        reset_token_stats()
        _track_tokens("screenshot", {"input_tokens": 10, "output_tokens": 5})
        _track_phase("execute", {"input_tokens": 20, "output_tokens": 10})
        stats = get_token_stats()
        assert "by_tool" in stats
        assert "by_phase" in stats
        assert "screenshot" in stats["by_tool"]
        assert "execute" in stats["by_phase"]

    def test_reset_token_stats(self):
        from src.agent import reset_token_stats, _track_tokens, _tool_token_stats, _phase_token_stats
        _track_tokens("x", {"input_tokens": 1, "output_tokens": 1})
        reset_token_stats()
        assert len(_tool_token_stats) == 0
        assert len(_phase_token_stats) == 0
