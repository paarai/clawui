"""Comprehensive unit tests for clawui.api with mocked backends.

Tests the public API layer in isolation by mocking underlying actions/helpers.
"""

import types
import pytest
from unittest.mock import patch, MagicMock, PropertyMock


# ---------------------------------------------------------------------------
# Desktop action wrappers
# ---------------------------------------------------------------------------

class TestClick:
    def test_click_no_args_raises(self):
        from clawui.api import click
        with pytest.raises(ValueError, match="Provide either"):
            click()

    @patch("clawui.api.find_elements")
    @patch("clawui.actions.click")
    def test_click_by_text(self, mock_click, mock_find):
        from clawui.api import click
        elem = MagicMock()
        elem.center = (100, 200)
        mock_find.return_value = [elem]
        click(text="OK")
        mock_find.assert_called_once_with(name="OK")
        mock_click.assert_called_once_with(x=100, y=200, button="left")

    @patch("clawui.actions.click")
    def test_click_by_coords(self, mock_click):
        from clawui.api import click
        click(coords=(50, 75))
        mock_click.assert_called_once_with(x=50, y=75, button="left")

    @patch("clawui.api.find_elements")
    def test_click_text_not_found_raises(self, mock_find):
        from clawui.api import click
        mock_find.return_value = []
        with pytest.raises(RuntimeError, match="No element found"):
            click(text="Nonexistent")


class TestDoubleClick:
    def test_no_args_raises(self):
        from clawui.api import double_click
        with pytest.raises(ValueError, match="Provide either"):
            double_click()

    @patch("clawui.api.find_elements")
    @patch("clawui.actions.double_click")
    def test_by_text(self, mock_dbl, mock_find):
        from clawui.api import double_click
        elem = MagicMock()
        elem.center = (10, 20)
        mock_find.return_value = [elem]
        double_click(text="file.txt")
        mock_dbl.assert_called_once_with(x=10, y=20)


class TestRightClick:
    @patch("clawui.api.find_elements")
    @patch("src.api._rclick", create=True)
    def test_by_text(self, mock_rclick, mock_find):
        # Test that right_click with text finds element and clicks
        from clawui import api
        elem = MagicMock()
        elem.center = (30, 40)
        mock_find.return_value = [elem]
        with patch.object(api, "_rclick", create=True) as m:
            # right_click imports internally, so we patch the actions module
            with patch("clawui.actions.right_click") as m2:
                api.right_click(text="item")
                mock_find.assert_called_with(name="item")

    @patch("clawui.actions.right_click")
    def test_no_args_calls_rclick(self, mock_rclick):
        from clawui.api import right_click
        right_click()
        mock_rclick.assert_called_once()


class TestTypeAndKeys:
    @patch("clawui.actions.type_text")
    def test_type_text(self, mock_type):
        from clawui.api import type_text
        type_text("hello")
        mock_type.assert_called_once_with("hello")

    @patch("clawui.actions.press_key")
    def test_press_key(self, mock_press):
        from clawui.api import press_key
        press_key("ctrl+s")
        mock_press.assert_called_once_with("ctrl+s")

    @patch("clawui.actions.hotkey")
    def test_hotkey(self, mock_hotkey):
        from clawui.api import hotkey
        hotkey("ctrl", "shift", "t")
        mock_hotkey.assert_called_once_with("ctrl", "shift", "t")


class TestScroll:
    @patch("clawui.actions.scroll")
    def test_scroll_default(self, mock_scroll):
        from clawui.api import scroll
        scroll()
        mock_scroll.assert_called_once_with("down", 3, x=None, y=None)

    @patch("clawui.actions.scroll")
    def test_scroll_with_coords(self, mock_scroll):
        from clawui.api import scroll
        scroll(direction="up", clicks=5, coords=(100, 200))
        mock_scroll.assert_called_once_with("up", 5, x=100, y=200)


class TestMouseMove:
    @patch("clawui.actions.mouse_move")
    def test_move(self, mock_move):
        from clawui.api import move_mouse
        move_mouse(123, 456)
        mock_move.assert_called_once_with(123, 456)


class TestDrag:
    @patch("clawui.actions.drag")
    def test_drag(self, mock_drag):
        from clawui.api import drag
        drag((10, 20), (30, 40))
        mock_drag.assert_called_once_with(10, 20, 30, 40)


# ---------------------------------------------------------------------------
# Window management
# ---------------------------------------------------------------------------

class TestWindowManagement:
    @patch("clawui.actions.focus_window")
    def test_focus_by_name(self, mock_focus):
        from clawui.api import focus_window
        focus_window(name="Firefox")
        mock_focus.assert_called_once_with(name="Firefox", window_id=None)

    @patch("clawui.actions.focus_window")
    def test_focus_by_id(self, mock_focus):
        from clawui.api import focus_window
        focus_window(window_id=12345)
        mock_focus.assert_called_once_with(name=None, window_id=12345)

    @patch("clawui.actions.get_active_window")
    def test_active_window(self, mock_active):
        from clawui.api import active_window
        mock_active.return_value = {"id": 1, "name": "Terminal"}
        result = active_window()
        assert result == {"id": 1, "name": "Terminal"}

    @patch("clawui.actions.minimize_window")
    def test_minimize(self, mock_min):
        from clawui.api import minimize
        minimize()
        mock_min.assert_called_once()

    @patch("clawui.actions.maximize_window")
    def test_maximize(self, mock_max):
        from clawui.api import maximize
        maximize()
        mock_max.assert_called_once()

    @patch("clawui.actions.close_window")
    def test_close(self, mock_close):
        from clawui.api import close
        close()
        mock_close.assert_called_once()


class TestWindows:
    @patch("clawui.x11_helper.list_windows")
    def test_windows_returns_list(self, mock_list):
        from clawui.api import windows
        mock_list.return_value = [{"id": 1, "name": "Test", "x": 0, "y": 0, "w": 800, "h": 600}]
        result = windows()
        assert len(result) == 1
        assert result[0]["name"] == "Test"


# ---------------------------------------------------------------------------
# Screenshot
# ---------------------------------------------------------------------------

class TestScreenshot:
    @patch("clawui.screenshot.take_screenshot")
    def test_screenshot_returns_bytes(self, mock_take):
        import base64
        from clawui.api import screenshot
        # take_screenshot returns a base64 string
        raw = b"\x89PNG..."
        mock_take.return_value = base64.b64encode(raw).decode()
        result = screenshot()
        assert result == raw

    @patch("clawui.screenshot.take_screenshot")
    def test_screenshot_save_to(self, mock_take, tmp_path):
        import base64
        from clawui.api import screenshot
        raw = b"\x89PNG..."
        mock_take.return_value = base64.b64encode(raw).decode()
        out = str(tmp_path / "test.png")
        screenshot(save_to=out)
        assert (tmp_path / "test.png").read_bytes() == raw


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------

class TestRetry:
    def test_retry_succeeds_on_second_attempt(self):
        from clawui.api import retry
        call_count = 0

        @retry(max_attempts=3, delay=0.01)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("transient")
            return "ok"

        assert flaky() == "ok"
        assert call_count == 2

    def test_retry_exhausts_attempts(self):
        from clawui.api import retry

        @retry(max_attempts=2, delay=0.01)
        def always_fails():
            raise RuntimeError("permanent")

        with pytest.raises(RuntimeError, match="permanent"):
            always_fails()

    def test_retry_does_not_catch_unrelated(self):
        from clawui.api import retry

        @retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        def wrong_error():
            raise TypeError("nope")

        with pytest.raises(TypeError):
            wrong_error()


# ---------------------------------------------------------------------------
# Browser API
# ---------------------------------------------------------------------------

class TestBrowserAPI:
    def test_singleton(self):
        from clawui.api import browser, _BrowserAPI
        assert isinstance(browser, _BrowserAPI)

    def test_connect_creates_helper(self):
        from clawui.api import _BrowserAPI
        b = _BrowserAPI()
        with patch("clawui.cdp_helper.CDPClient") as MockCDP:
            mock_instance = MagicMock()
            MockCDP.return_value = mock_instance
            b.connect(port=9222)
            MockCDP.assert_called_once_with(port=9222)
            mock_instance.connect.assert_called_once()

    def test_navigate_calls_helper(self):
        from clawui.api import _BrowserAPI
        b = _BrowserAPI()
        mock_helper = MagicMock()
        b._helper = mock_helper
        with patch("time.sleep"):
            b.navigate("https://example.com", wait=True)
        mock_helper.navigate.assert_called_once_with("https://example.com")

    def test_get_html(self):
        from clawui.api import _BrowserAPI
        b = _BrowserAPI()
        mock_helper = MagicMock()
        mock_helper.evaluate.return_value = {
            "result": {"value": "<html><body>Hello</body></html>"}
        }
        b._helper = mock_helper
        result = b.get_html()
        assert "Hello" in result


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

def test_version():
    import clawui
    assert clawui.__version__ == "0.9.0"


def test_enable_logging():
    import logging
    import clawui
    clawui.enable_logging(logging.WARNING)
    logger = logging.getLogger("clawui")
    assert logger.level == logging.WARNING
    # Call again to test idempotency (no duplicate handlers)
    handler_count = len(logger.handlers)
    clawui.enable_logging(logging.WARNING)
    assert len(logger.handlers) == handler_count
