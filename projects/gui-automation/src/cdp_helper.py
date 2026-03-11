"""
CDP (Chrome DevTools Protocol) helper for browser automation.
Connects to a running Chrome/Chromium instance with remote debugging enabled.
"""

import websocket
import json
import time
from typing import Optional

class CDPClient:
    """A basic client for the Chrome DevTools Protocol."""

    def __init__(self, websocket_url: str):
        self._ws_url = websocket_url
        self._ws = None
        self._request_id = 0
        self._responses = {}

    def connect(self):
        """Connect to the WebSocket."""
        try:
            self._ws = websocket.create_connection(self._ws_url)
            print("Connected to CDP WebSocket.")
        except Exception as e:
            print(f"Failed to connect to CDP: {e}")
            raise

    def close(self):
        """Close the WebSocket connection."""
        if self._ws:
            self._ws.close()
            self._ws = None
            print("CDP connection closed.")

    def _send_request(self, method: str, params: Optional[dict] = None) -> int:
        """Send a request to the browser."""
        if not self._ws:
            raise ConnectionError("Not connected to CDP.")
        self._request_id += 1
        req_id = self._request_id
        request = {
            "id": req_id,
            "method": method,
            "params": params or {}
        }
        self._ws.send(json.dumps(request))
        return req_id

    def _wait_for_response(self, request_id: int, timeout: int = 5) -> dict:
        """Wait for a response to a specific request."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                message = self._ws.recv()
                response = json.loads(message)
                if "id" in response and response["id"] == request_id:
                    return response.get("result", {})
                # Store other messages if needed later
            except websocket.WebSocketTimeoutException:
                continue
            except Exception as e:
                print(f"Error receiving CDP message: {e}")
                break
        raise TimeoutError(f"Timeout waiting for response to request {request_id}")

    def navigate(self, url: str) -> dict:
        """Navigate to a URL."""
        req_id = self._send_request("Page.navigate", {"url": url})
        return self._wait_for_response(req_id)

    def get_document(self) -> dict:
        """Get the root document node."""
        req_id = self._send_request("DOM.getDocument", {"depth": -1})
        return self._wait_for_response(req_id)

    def query_selector(self, node_id: int, selector: str) -> dict:
        """Query for a node using a CSS selector."""
        req_id = self._send_request("DOM.querySelector", {"nodeId": node_id, "selector": selector})
        return self._wait_for_response(req_id)

    def get_box_model(self, node_id: int) -> dict:
        """Get the box model for a node to find its coordinates."""
        req_id = self._send_request("DOM.getBoxModel", {"nodeId": node_id})
        return self._wait_for_response(req_id)

    def click(self, x: int, y: int):
        """Simulate a mouse click at coordinates."""
        self._send_request("Input.dispatchMouseEvent", {
            "type": "mousePressed",
            "x": x,
            "y": y,
            "button": "left",
            "clickCount": 1
        })
        time.sleep(0.05)
        self._send_request("Input.dispatchMouseEvent", {
            "type": "mouseReleased",
            "x": x,
            "y": y,
            "button": "left",
            "clickCount": 1
        })

    def type_text(self, text: str):
        """Simulate typing text."""
        for char in text:
            self._send_request("Input.dispatchKeyEvent", {
                "type": "char",
                "text": char
            })
            time.sleep(0.02)

def find_chromium_and_get_cdp_url() -> Optional[str]:
    """
    Find a running Chromium instance with remote debugging and get its CDP WebSocket URL.
    This is a placeholder. A real implementation would need to parse /json/version endpoint.
    """
    # This would typically involve an HTTP request to http://localhost:9222/json/version
    # For now, we'll hardcode a common URL for simplicity.
    # In a real scenario, you'd launch chromium with:
    # chromium-browser --remote-debugging-port=9222
    
    # Placeholder URL
    return "ws://localhost:9222/devtools/browser/some-uuid"

if __name__ == '__main__':
    # Example usage - this part is for demonstration and testing
    
    # In a real script, you'd get this URL dynamically
    # url = find_chromium_and_get_cdp_url()
    # if not url:
    #     print("Could not find a debuggable Chromium instance.")
    #     print("Launch with: chromium-browser --remote-debugging-port=9222")
    #     sys.exit(1)
        
    # client = CDPClient(url)
    # try:
    #     client.connect()
    #     client.navigate("https://github.com/new")
    #     time.sleep(2)
        
    #     doc = client.get_document()
    #     root_node_id = doc['root']['nodeId']
        
    #     # Find repo name input field
    #     repo_name_node = client.query_selector(root_node_id, 'input[name="repository[name]"]')
    #     if 'nodeId' in repo_name_node:
    #         node_id = repo_name_node['nodeId']
    #         box = client.get_box_model(node_id)
    #         content = box['model']['content']
    #         # Click in the middle of the input field
    #         click_x = content[0] + (content[2] - content[0]) / 2
    #         click_y = content[1] + (content[5] - content[1]) / 2
    #         client.click(int(click_x), int(click_y))
    #         time.sleep(0.5)
    #         client.type_text("test-repo-via-cdp")
    #     else:
    #         print("Could not find repository name input field.")

    # finally:
    #     client.close()
    
    print("CDP helper structure created. Needs websocket-client library and a running Chromium with remote debugging.")
    pass
