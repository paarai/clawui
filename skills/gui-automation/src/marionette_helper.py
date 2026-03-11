"""
Marionette backend for Firefox browser automation.
Marionette is Firefox's built-in remote control protocol (similar to CDP for Chromium).
Start Firefox with: firefox --marionette
Default port: 2828
"""

import json
import socket
import subprocess
import time
import os
from typing import Optional, List, Dict, Any


class MarionetteClient:
    """Simple Marionette protocol client for Firefox automation."""

    def __init__(self, host: str = "127.0.0.1", port: int = 2828):
        self.host = host
        self.port = port
        self._sock: Optional[socket.socket] = None
        self._msg_id = 0

    def _connect(self) -> bool:
        """Connect to Marionette server."""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(10)
            self._sock.connect((self.host, self.port))
            # Read server hello
            hello = self._recv()
            return hello is not None
        except Exception:
            self._sock = None
            return False

    def _recv(self) -> Optional[Any]:
        """Receive a Marionette message (length-prefixed JSON)."""
        try:
            data = b""
            # Read until we get the length prefix (digits followed by ':')
            while b":" not in data:
                chunk = self._sock.recv(1)
                if not chunk:
                    return None
                data += chunk
            length_str, _, remainder = data.partition(b":")
            length = int(length_str)
            # Read the JSON body
            body = remainder
            while len(body) < length:
                chunk = self._sock.recv(length - len(body))
                if not chunk:
                    return None
                body += chunk
            return json.loads(body)
        except Exception:
            return None

    def _send(self, command: str, params: dict = None) -> Optional[Any]:
        """Send a Marionette command and return the response."""
        if not self._sock:
            if not self._connect():
                return None
        self._msg_id += 1
        msg = [0, self._msg_id, command, params or {}]
        encoded = json.dumps(msg).encode()
        packet = f"{len(encoded)}:".encode() + encoded
        try:
            self._sock.sendall(packet)
            return self._recv()
        except Exception:
            return None

    def is_available(self) -> bool:
        """Check if Marionette endpoint is reachable."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((self.host, self.port))
            sock.close()
            return True
        except Exception:
            return False

    def new_session(self) -> Optional[str]:
        """Create a new Marionette session."""
        result = self._send("WebDriver:NewSession", {
            "capabilities": {"alwaysMatch": {"acceptInsecureCerts": True}}
        })
        if result and len(result) > 3:
            return result[3].get("sessionId") if isinstance(result[3], dict) else None
        return None

    def navigate(self, url: str) -> bool:
        """Navigate to URL."""
        result = self._send("WebDriver:Navigate", {"url": url})
        return result is not None

    def get_url(self) -> str:
        """Get current page URL."""
        result = self._send("WebDriver:GetCurrentURL", {})
        if result and len(result) > 3:
            return result[3].get("value", "") if isinstance(result[3], dict) else ""
        return ""

    def get_title(self) -> str:
        """Get current page title."""
        result = self._send("WebDriver:GetTitle", {})
        if result and len(result) > 3:
            return result[3].get("value", "") if isinstance(result[3], dict) else ""
        return ""

    def find_element(self, strategy: str, selector: str) -> Optional[str]:
        """Find element. strategy: 'css selector', 'id', 'xpath', 'name', 'tag name'."""
        result = self._send("WebDriver:FindElement", {
            "using": strategy, "value": selector
        })
        if result and len(result) > 3 and isinstance(result[3], dict):
            # Element reference is in ELEMENT key or element-xxx key
            val = result[3].get("value", result[3])
            if isinstance(val, dict):
                # Return the element ID (first value in dict)
                for k, v in val.items():
                    return v
        return None

    def find_elements(self, strategy: str, selector: str) -> List[str]:
        """Find multiple elements."""
        result = self._send("WebDriver:FindElements", {
            "using": strategy, "value": selector
        })
        elements = []
        if result and len(result) > 3 and isinstance(result[3], list):
            for item in result[3]:
                if isinstance(item, dict):
                    for k, v in item.items():
                        elements.append(v)
                        break
        return elements

    def click_element(self, element_id: str) -> bool:
        """Click an element by its ID."""
        result = self._send("WebDriver:ElementClick", {
            "id": element_id
        })
        return result is not None

    def send_keys(self, element_id: str, text: str) -> bool:
        """Type text into element."""
        result = self._send("WebDriver:ElementSendKeys", {
            "id": element_id, "text": text
        })
        return result is not None

    def execute_script(self, script: str, args: list = None) -> Any:
        """Execute JavaScript in the browser."""
        result = self._send("WebDriver:ExecuteScript", {
            "script": script, "args": args or []
        })
        if result and len(result) > 3:
            return result[3].get("value") if isinstance(result[3], dict) else result[3]
        return None

    def take_screenshot(self) -> Optional[str]:
        """Take a screenshot, returns base64 PNG."""
        result = self._send("WebDriver:TakeScreenshot", {})
        if result and len(result) > 3 and isinstance(result[3], dict):
            data = result[3].get("value", "")
            # Remove data:image/png;base64, prefix if present
            if data.startswith("data:"):
                data = data.split(",", 1)[1]
            return data
        return None

    def get_window_handles(self) -> List[str]:
        """Get all window/tab handles."""
        result = self._send("WebDriver:GetWindowHandles", {})
        if result and len(result) > 3:
            return result[3] if isinstance(result[3], list) else []
        return []

    def switch_to_window(self, handle: str) -> bool:
        """Switch to a window/tab by handle."""
        result = self._send("WebDriver:SwitchToWindow", {"handle": handle})
        return result is not None

    def close_window(self) -> bool:
        """Close current window/tab."""
        result = self._send("WebDriver:CloseWindow", {})
        return result is not None

    def close(self):
        """Close the connection."""
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None


def get_or_create_marionette_client(port: int = 2828) -> Optional[MarionetteClient]:
    """Get a Marionette client, starting Firefox if needed."""
    client = MarionetteClient(port=port)
    if client.is_available():
        return client

    # Try to start Firefox with Marionette
    try:
        display = os.environ.get("DISPLAY", ":0")
        subprocess.Popen(
            ["firefox", "--marionette", "--no-remote"],
            env={**os.environ, "DISPLAY": display},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        # Wait for Marionette to become available
        for _ in range(15):
            time.sleep(1)
            if client.is_available():
                return client
    except Exception:
        pass
    return None
