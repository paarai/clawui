"""Multi-model AI backend for GUI automation."""

import os
import json
import base64
import time as _time
import sys
from abc import ABC, abstractmethod
from functools import wraps

# --- P4-A: Backend rate limiting & retry ---
_API_RETRY_MAX = int(os.getenv("CLAWUI_API_RETRY_MAX", "3"))
_API_RETRY_DELAY = float(os.getenv("CLAWUI_API_RETRY_DELAY", "1.0"))


def _with_api_retry(func=None, *, max_retries=None, initial_delay=None):
    """Decorator: exponential backoff retry for transient API errors (429, 503, timeout).

    Catches provider-specific rate-limit / connection errors via lazy isinstance
    checks so the decorator works even when SDK packages are not installed.
    """
    max_retries = max_retries if max_retries is not None else _API_RETRY_MAX
    initial_delay = initial_delay if initial_delay is not None else _API_RETRY_DELAY

    def _is_retryable(exc):
        """Return True for transient errors worth retrying."""
        # Check by exception class name (avoids hard imports)
        cls_name = type(exc).__name__
        if cls_name in ("RateLimitError", "APIConnectionError", "APITimeoutError",
                        "InternalServerError", "APIStatusError"):
            # For APIStatusError, only retry 429 / 5xx
            status = getattr(exc, "status_code", None)
            if status is not None:
                return status == 429 or status >= 500
            return True
        # stdlib / generic timeouts
        if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
            return True
        return False

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_err = None
            for attempt in range(max_retries):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    if not _is_retryable(e) or attempt >= max_retries - 1:
                        raise
                    print(f"[WARN] {fn.__qualname__}: {e} (attempt {attempt+1}/{max_retries}), "
                          f"retrying in {delay:.1f}s...", file=sys.stderr)
                    _time.sleep(delay)
                    delay *= 2
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


class AIBackend(ABC):
    """Abstract AI backend for GUI decisions."""

    @abstractmethod
    def chat(self, messages: list, tools: list, system: str) -> dict:
        """Send messages and get response with tool calls.
        
        Returns: {
            "text": str | None,
            "tool_calls": [{"id": str, "name": str, "input": dict}]
        }
        """
        pass


class ClaudeBackend(AIBackend):
    """Anthropic Claude backend."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        from anthropic import Anthropic
        self.client = Anthropic()
        self.model = model

    @_with_api_retry
    def chat(self, messages, tools, system):
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            tools=tools,
            messages=messages,
        )

        text = None
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                text = block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        return {"text": text, "tool_calls": tool_calls, "raw_content": response.content}


class OpenAIBackend(AIBackend):
    """OpenAI GPT-4o backend."""

    def __init__(self, model: str = "gpt-4o"):
        from openai import OpenAI
        self.client = OpenAI()
        self.model = model

    def _convert_tools(self, tools):
        """Convert Anthropic tool format to OpenAI function format."""
        functions = []
        for tool in tools:
            functions.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool["input_schema"],
                }
            })
        return functions

    def _convert_messages(self, messages, system):
        """Convert message format."""
        oai_messages = [{"role": "system", "content": system}]

        for msg in messages:
            if msg["role"] == "assistant":
                # Handle tool use blocks
                content = msg["content"]
                if isinstance(content, list):
                    text_parts = []
                    tool_calls = []
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                text_parts.append(block["text"])
                            elif block.get("type") == "tool_use":
                                tool_calls.append({
                                    "id": block["id"],
                                    "type": "function",
                                    "function": {
                                        "name": block["name"],
                                        "arguments": json.dumps(block["input"]),
                                    }
                                })
                    oai_msg = {"role": "assistant"}
                    if text_parts:
                        oai_msg["content"] = "\n".join(text_parts)
                    if tool_calls:
                        oai_msg["tool_calls"] = tool_calls
                    oai_messages.append(oai_msg)
                else:
                    oai_messages.append({"role": "assistant", "content": content})

            elif msg["role"] == "user":
                content = msg["content"]
                if isinstance(content, list):
                    # Tool results
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            tool_content = block.get("content", "")
                            if isinstance(tool_content, list):
                                # Handle image results
                                parts = []
                                for part in tool_content:
                                    if part.get("type") == "image":
                                        parts.append({
                                            "type": "image_url",
                                            "image_url": {
                                                "url": f"data:image/png;base64,{part['source']['data']}"
                                            }
                                        })
                                    elif part.get("type") == "text":
                                        parts.append({"type": "text", "text": part["text"]})
                                tool_content = json.dumps(parts) if not any(p.get("type") == "image_url" for p in parts) else str(parts)
                            oai_messages.append({
                                "role": "tool",
                                "tool_call_id": block["tool_use_id"],
                                "content": str(tool_content),
                            })
                else:
                    oai_messages.append({"role": "user", "content": content})

        return oai_messages

    @_with_api_retry
    def chat(self, messages, tools, system):
        oai_tools = self._convert_tools(tools)
        oai_messages = self._convert_messages(messages, system)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=oai_messages,
            tools=oai_tools,
            max_tokens=4096,
        )

        choice = response.choices[0]
        text = choice.message.content
        tool_calls = []

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "input": json.loads(tc.function.arguments),
                })

        # Convert back to Anthropic-style content blocks for uniform handling
        raw_content = []
        if text:
            raw_content.append(type("Block", (), {"type": "text", "text": text})())
        for tc in tool_calls:
            raw_content.append(type("Block", (), {
                "type": "tool_use", "id": tc["id"],
                "name": tc["name"], "input": tc["input"]
            })())

        return {"text": text, "tool_calls": tool_calls, "raw_content": raw_content}


class AnyRouterBackend(AIBackend):
    """AnyRouter backend (Anthropic-compatible API used by OpenClaw)."""

    def __init__(self, model: str = "claude-opus-4-6"):
        from anthropic import Anthropic
        api_key = os.environ.get("ANYROUTER_API_KEY", "")
        base_url = os.environ.get("ANYROUTER_BASE_URL", "https://anyrouter.top")
        # Try loading from openclaw config if env not set
        if not api_key:
            try:
                import json
                with open(os.path.expanduser("~/.openclaw/agents/main/agent/models.json")) as f:
                    cfg = json.load(f)
                ar = cfg.get("providers", {}).get("anyrouter", {})
                api_key = ar.get("apiKey", "")
                base_url = ar.get("baseUrl", base_url)
            except Exception:
                pass
        self.client = Anthropic(api_key=api_key, base_url=base_url)
        self.model = model

    @_with_api_retry
    def chat(self, messages, tools, system):
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            tools=tools,
            messages=messages,
        )

        text = None
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                text = block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        return {"text": text, "tool_calls": tool_calls, "raw_content": response.content}


class OllamaBackend(AIBackend):
    """Local Ollama backend (OpenAI-compatible API)."""

    def __init__(self, model: str = "llava:7b"):
        from openai import OpenAI
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.client = OpenAI(api_key="ollama", base_url=f"{base_url}/v1")
        self.model = model
        self._oai_helper = OpenAIBackend.__new__(OpenAIBackend)
        self._oai_helper.client = self.client
        self._oai_helper.model = self.model

    def chat(self, messages, tools, system):
        return self._oai_helper.chat(messages, tools, system)


class GeminiBackend(AIBackend):
    """Google Gemini backend via OpenAI-compatible API."""

    def __init__(self, model: str = "gemini-2.5-flash"):
        from openai import OpenAI
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        self.model = model
        # Reuse OpenAI conversion logic
        self._oai = OpenAIBackend.__new__(OpenAIBackend)
        self._oai.client = self.client
        self._oai.model = self.model

    def chat(self, messages, tools, system):
        return self._oai.chat(messages, tools, system)
    # Borrow conversion methods
    _convert_tools = OpenAIBackend._convert_tools
    _convert_messages = OpenAIBackend._convert_messages


def get_backend(model: str = None, model_override: str = None) -> AIBackend:
    """Get appropriate AI backend based on model name."""
    model = model_override or model or os.getenv("GUI_AI_MODEL", "claude-sonnet-4-20250514")

    if "claude" in model or "anthropic" in model:
        return ClaudeBackend(model=model)
    elif "gemini" in model:
        return GeminiBackend(model=model)
    elif "gpt" in model or "openai" in model:
        return OpenAIBackend(model=model)
    elif "llava" in model or "llama" in model or "qwen" in model or "ollama" in model:
        return OllamaBackend(model=model)
    else:
        # Default: try AnyRouter (OpenClaw's built-in backend)
        try:
            return AnyRouterBackend(model=model)
        except Exception:
            return ClaudeBackend(model=model)
