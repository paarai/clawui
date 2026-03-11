"""Vision backend for GUI automation using OpenAI-compatible API (Ollama, OpenAI, etc.)."""

import base64
import json
import os
import subprocess
import time
from typing import Optional, List, Dict, Any

import httpx
from .backends import AIBackend

# Optional: httpx for async; we use sync


class VisionBackend(AIBackend):
    """Vision-enabled AI backend using OpenAI-compatible chat completions with image support."""

    def __init__(
        self,
        api_base: str = "http://localhost:11434/v1",  # Ollama default
        api_key: str = "",
        model: str = "llava:7b",  # default Ollama vision model
        temperature: float = 0.3,
        max_tokens: int = 1024,
        **kwargs
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = httpx.Client(timeout=httpx.Timeout(30.0))

    def _encode_image(self, b64_data: str) -> str:
        """Ensure image is data URL with proper mime type."""
        if b64_data.startswith("data:"):
            return b64_data
        return f"data:image/png;base64,{b64_data}"

    def chat(self, messages: List[Dict], tools: List[Dict], system: str) -> Dict[str, Any]:
        """
        Run vision-capable chat. Expects messages to potentially include image_url entries.
        Returns dict with 'text' containing JSON tool_calls.
        """
        # Prepare messages: prepend system if needed
        prefixed = []
        if system:
            prefixed.append({"role": "system", "content": system})
        prefixed.extend(messages)

        payload = {
            "model": self.model,
            "messages": prefixed,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            resp = self.client.post(
                f"{self.api_base}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            text = choice["message"].get("content", "")
            # No native tool_calls; assume model returns JSON instructions in text
            return {"text": text, "tool_calls": []}
        except Exception as e:
            return {"text": f"VisionBackend error: {e}", "tool_calls": []}

    def __del__(self):
        try:
            self.client.close()
        except:
            pass


class OllamaVisionBackend(VisionBackend):
    """Specific backend for Ollama (uses /api/generate for some models, but /v1/chat/completions works too)."""

    def __init__(self, **kwargs):
        # Force Ollama default endpoint if not specified
        base = kwargs.pop("api_base", "http://localhost:11434/v1")
        super().__init__(api_base=base, **kwargs)


class OpenAIVisionBackend(VisionBackend):
    """Backend for OpenAI GPT-4o / GPT-4-turbo with vision."""

    def __init__(self, api_key: str = "", model: str = "gpt-4o", **kwargs):
        base = kwargs.pop("api_base", "https://api.openai.com/v1")
        super().__init__(api_base=base, api_key=api_key, model=model, **kwargs)


def get_vision_backend(**kwargs) -> VisionBackend:
    """Factory to create vision backend from config."""
    backend_type = kwargs.pop("type", "ollama")
    if backend_type == "ollama":
        return OllamaVisionBackend(**kwargs)
    elif backend_type == "openai":
        return OpenAIVisionBackend(**kwargs)
    else:
        return VisionBackend(**kwargs)
