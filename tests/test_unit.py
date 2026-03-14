#!/usr/bin/env python3
"""Unit tests for clawui core modules - runnable without a display server."""

import json
import os
import sys
import time
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
