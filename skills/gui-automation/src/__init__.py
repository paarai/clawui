"""ClawUI - AI-driven desktop and browser automation for Linux.

Quick start:
    from clawui.api import screenshot, click, type_text, browser, apps, tree

Full API:
    from clawui.api import (
        # Desktop perception
        screenshot, apps, tree, find_elements, focused_element, ocr, windows,
        # Mouse actions
        click, double_click, right_click, drag, scroll, move_mouse,
        # Keyboard actions
        type_text, press_key, hotkey,
        # Window management
        focus_window, active_window, minimize, maximize, close,
        # Wait helpers
        wait_for_element, wait_for_text,
        # Retry decorator (for custom automation scripts)
        retry,
        # Browser (CDP)
        browser,
    )
"""

__version__ = "0.8.0"
