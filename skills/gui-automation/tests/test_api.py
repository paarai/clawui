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
    from src.api import browser, _BrowserAPI
    assert isinstance(browser, _BrowserAPI)


def test_apps_returns_list():
    """apps() should return a list of strings."""
    from src.api import apps
    result = apps()
    assert isinstance(result, list)
    # On a desktop with AT-SPI, should have at least one app
    # (may be empty in headless CI, but should not raise)


def test_tree_returns_string():
    """tree() should return a string."""
    from src.api import tree
    result = tree()
    assert isinstance(result, str)


def test_click_requires_args():
    """click() without text or coords should raise ValueError."""
    from src.api import click
    with pytest.raises(ValueError, match="Provide either"):
        click()


def test_double_click_requires_args():
    """double_click() without text or coords should raise ValueError."""
    from src.api import double_click
    with pytest.raises(ValueError, match="Provide either"):
        double_click()
