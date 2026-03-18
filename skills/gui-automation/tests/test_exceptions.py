"""Tests for clawui.exceptions — structured exception hierarchy."""

import pytest
from clawui.exceptions import (
    ClawUIError,
    BackendError, CDPError, MarionetteError, ATSPIError, X11Error, YdotoolError,
    PerceptionError, ElementNotFoundError, TextNotFoundError, ScreenshotError,
    TimeoutError, WaitTimeoutError,
    AgentError, ModelError,
    ConfigError,
)


# -- Hierarchy tests ---------------------------------------------------------

class TestHierarchy:
    """Verify that exception subclasses are properly chained."""

    @pytest.mark.parametrize("cls,parent", [
        (BackendError, ClawUIError),
        (CDPError, BackendError),
        (MarionetteError, BackendError),
        (ATSPIError, BackendError),
        (X11Error, BackendError),
        (YdotoolError, BackendError),
        (PerceptionError, ClawUIError),
        (ElementNotFoundError, PerceptionError),
        (TextNotFoundError, PerceptionError),
        (ScreenshotError, PerceptionError),
        (TimeoutError, ClawUIError),
        (WaitTimeoutError, TimeoutError),
        (AgentError, ClawUIError),
        (ModelError, AgentError),
        (ConfigError, ClawUIError),
    ])
    def test_subclass(self, cls, parent):
        assert issubclass(cls, parent)
        assert issubclass(cls, ClawUIError)

    def test_catch_all_with_clawui_error(self):
        """All typed exceptions should be catchable via ClawUIError."""
        for exc_cls in [CDPError, MarionetteError, ATSPIError, X11Error, YdotoolError,
                        ElementNotFoundError, TextNotFoundError, ScreenshotError,
                        WaitTimeoutError, ModelError, ConfigError]:
            with pytest.raises(ClawUIError):
                raise exc_cls("test")

    def test_backend_errors_caught_by_backend_error(self):
        for exc_cls in [CDPError, MarionetteError, ATSPIError, X11Error, YdotoolError]:
            with pytest.raises(BackendError):
                raise exc_cls("test")


# -- Rich exception attributes ----------------------------------------------

class TestElementNotFoundError:
    def test_default_message(self):
        e = ElementNotFoundError("OK button")
        assert "OK button" in str(e)
        assert e.query == "OK button"

    def test_custom_message(self):
        e = ElementNotFoundError("btn", message="Custom msg")
        assert str(e) == "Custom msg"
        assert e.query == "btn"

    def test_empty(self):
        e = ElementNotFoundError()
        assert e.query == ""


class TestTextNotFoundError:
    def test_default_message(self):
        e = TextNotFoundError("Submit")
        assert "Submit" in str(e)
        assert e.text == "Submit"

    def test_custom_message(self):
        e = TextNotFoundError("x", message="Oops")
        assert str(e) == "Oops"


class TestTimeoutError:
    def test_attrs(self):
        e = TimeoutError(operation="navigate", seconds=10.0)
        assert e.operation == "navigate"
        assert e.seconds == 10.0
        assert "10" in str(e)
        assert "navigate" in str(e)

    def test_custom_message(self):
        e = TimeoutError(message="Custom timeout")
        assert str(e) == "Custom timeout"


class TestWaitTimeoutError:
    def test_inherits_timeout(self):
        e = WaitTimeoutError(operation="wait_for_element", seconds=5)
        assert isinstance(e, TimeoutError)
        assert isinstance(e, ClawUIError)
        assert e.seconds == 5


# -- Serialization / repr ---------------------------------------------------

class TestRepr:
    def test_str_roundtrip(self):
        """All exceptions should have meaningful str() output."""
        cases = [
            ClawUIError("generic"),
            CDPError("connection refused"),
            ElementNotFoundError("Save"),
            TimeoutError(operation="click", seconds=3),
        ]
        for exc in cases:
            s = str(exc)
            assert len(s) > 0
            assert isinstance(s, str)
