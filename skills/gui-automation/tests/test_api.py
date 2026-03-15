"""Tests for the public Python API (src/api.py)."""

import importlib
import pytest


def test_api_imports():
    """All public API symbols should be importable."""
    from src import api
    # Desktop
    assert callable(api.screenshot)
    assert callable(api.apps)
    assert callable(api.tree)
    assert callable(api.find_elements)
    assert callable(api.focused_element)
    assert callable(api.click)
    assert callable(api.double_click)
    assert callable(api.type_text)
    assert callable(api.press_key)
    assert callable(api.scroll)
    assert callable(api.move_mouse)
    assert callable(api.windows)
    # Browser
    assert hasattr(api.browser, 'navigate')
    assert hasattr(api.browser, 'click_text')
    assert hasattr(api.browser, 'get_html')
    assert hasattr(api.browser, 'screenshot')
    assert hasattr(api.browser, 'tabs')
    assert hasattr(api.browser, 'wait_for')
    # OCR
    assert callable(api.ocr)
    # Wait helpers
    assert callable(api.wait_for_element)
    assert callable(api.wait_for_text)


def test_api_module_docstring():
    """API module should have usage examples in docstring."""
    from src import api
    assert "from clawui.api import" in api.__doc__
    assert "screenshot" in api.__doc__
    assert "browser.navigate" in api.__doc__


def test_browser_api_singleton():
    """browser should be a singleton _BrowserAPI instance."""
    from clawui.api import browser, _BrowserAPI
    assert isinstance(browser, _BrowserAPI)


def test_apps_returns_list():
    """apps() should return a list of strings."""
    from clawui.api import apps
    result = apps()
    assert isinstance(result, list)
    # On a desktop with AT-SPI, should have at least one app
    # (may be empty in headless CI, but should not raise)


def test_tree_returns_string():
    """tree() should return a string."""
    from clawui.api import tree
    result = tree()
    assert isinstance(result, str)


def test_click_requires_args():
    """click() without text or coords should raise ValueError."""
    from clawui.api import click
    with pytest.raises(ValueError, match="Provide either"):
        click()


def test_double_click_requires_args():
    """double_click() without text or coords should raise ValueError."""
    from clawui.api import double_click
    with pytest.raises(ValueError, match="Provide either"):
        double_click()


def test_annotate_import():
    """annotate() and click_index() should be importable from the API."""
    from clawui.api import annotate, click_index
    assert callable(annotate)
    assert callable(click_index)


def test_click_index_no_annotation():
    """click_index() should raise RuntimeError if no annotation taken."""
    from clawui.api import click_index
    from clawui.annotated_screenshot import _last_elements
    # Clear any cached elements
    _last_elements.clear()
    with pytest.raises(RuntimeError, match="No annotated screenshot"):
        click_index(1)


def test_annotated_screenshot_dedup():
    """Deduplication should remove overlapping elements."""
    from clawui.annotated_screenshot import _dedup_elements
    elements = [
        {"x": 100, "y": 100, "width": 50, "height": 30, "role": "button", "name": "A"},
        {"x": 102, "y": 101, "width": 50, "height": 30, "role": "button", "name": "A"},  # duplicate
        {"x": 300, "y": 100, "width": 50, "height": 30, "role": "button", "name": "B"},
    ]
    result = _dedup_elements(elements)
    assert len(result) == 2  # duplicate removed


def test_run_agent_timeout_signature():
    """run_agent should accept a timeout parameter."""
    import inspect
    from clawui.agent import run_agent
    sig = inspect.signature(run_agent)
    assert "timeout" in sig.parameters, "run_agent must accept 'timeout' parameter"
    assert sig.parameters["timeout"].default is None, "timeout default should be None"
