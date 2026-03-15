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

import logging

__version__ = "0.8.2"

logging.getLogger("clawui").addHandler(logging.NullHandler())


def enable_logging(level=logging.DEBUG):
    """Enable clawui logging to stderr with a readable format."""
    logger = logging.getLogger("clawui")
    logger.setLevel(level)

    has_stream_handler = any(
        isinstance(h, logging.StreamHandler) and getattr(h, "_clawui_handler", False)
        for h in logger.handlers
    )
    if not has_stream_handler:
        handler = logging.StreamHandler()
        handler._clawui_handler = True  # type: ignore[attr-defined]
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        ))
        logger.addHandler(handler)
