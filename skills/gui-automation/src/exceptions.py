"""ClawUI exception hierarchy for reliable error handling.

Users can catch specific exception types to handle different failure modes:

    from clawui.exceptions import CDPError, ElementNotFoundError

    try:
        api.click_element(5)
    except ElementNotFoundError:
        print("Element not on screen")
    except CDPError:
        print("Browser connection issue")
    except ClawUIError:
        print("Some other ClawUI error")
"""


class ClawUIError(Exception):
    """Base exception for all ClawUI errors."""


# -- Backend errors ----------------------------------------------------------

class BackendError(ClawUIError):
    """A backend (AT-SPI, X11, CDP, Marionette, ydotool) failed."""


class CDPError(BackendError):
    """Chrome DevTools Protocol error (connection lost, command rejected, etc.)."""


class MarionetteError(BackendError):
    """Firefox Marionette protocol error."""


class ATSPIError(BackendError):
    """AT-SPI accessibility backend error."""


class X11Error(BackendError):
    """X11/xdotool backend error."""


class YdotoolError(BackendError):
    """ydotool (Wayland) backend error."""


# -- Perception / element errors ---------------------------------------------

class PerceptionError(ClawUIError):
    """Error during screen perception (screenshot, OCR, element detection)."""


class ElementNotFoundError(PerceptionError):
    """Requested UI element was not found on screen."""

    def __init__(self, query: str = "", message: str | None = None):
        self.query = query
        super().__init__(message or f"Element not found: {query!r}")


class TextNotFoundError(PerceptionError):
    """OCR text search found no matches."""

    def __init__(self, text: str = "", message: str | None = None):
        self.text = text
        super().__init__(message or f"Text not found on screen: {text!r}")


class ScreenshotError(PerceptionError):
    """Failed to capture a screenshot."""


# -- Timeout errors ----------------------------------------------------------

class TimeoutError(ClawUIError):  # noqa: A001 – intentional shadow of builtin
    """An operation exceeded its timeout."""

    def __init__(self, operation: str = "", seconds: float = 0, message: str | None = None):
        self.operation = operation
        self.seconds = seconds
        super().__init__(message or f"Timeout after {seconds}s: {operation}")


class WaitTimeoutError(TimeoutError):
    """wait_for_element / wait_for_text exceeded its timeout."""


# -- Agent errors ------------------------------------------------------------

class AgentError(ClawUIError):
    """Error in the AI agent loop."""


class ModelError(AgentError):
    """LLM API call failed (auth, rate limit, bad response, etc.)."""


# -- Configuration errors ----------------------------------------------------

class ConfigError(ClawUIError):
    """Invalid or missing configuration."""
