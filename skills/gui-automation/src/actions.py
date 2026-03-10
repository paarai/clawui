"""Actions module - execute mouse, keyboard, and window operations."""

import subprocess
import shlex
import asyncio
import shutil

TYPING_DELAY_MS = 12
TYPING_CHUNK_SIZE = 50


def _run(cmd: str, **kwargs) -> subprocess.CompletedProcess:
    """Run a shell command."""
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kwargs)


def _is_wayland() -> bool:
    import os
    return os.environ.get("XDG_SESSION_TYPE") == "wayland"


def _get_tool() -> str:
    """Select input tool. Prefer xdotool (works via XWayland even on Wayland)."""
    if shutil.which("xdotool"):
        return "xdotool"
    if shutil.which("ydotool"):
        return "ydotool"
    raise RuntimeError("No input tool found. Install xdotool or ydotool.")


# === Mouse Actions ===

def _ensure_display():
    """Ensure DISPLAY is set for xdotool on Wayland."""
    import os
    if not os.environ.get("DISPLAY"):
        os.environ["DISPLAY"] = ":0"


def mouse_move(x: int, y: int):
    """Move mouse to absolute position."""
    _ensure_display()
    tool = _get_tool()
    if tool == "xdotool":
        _run(f"xdotool mousemove --sync {x} {y}")
    else:
        _run(f"ydotool mousemove {x} {y}")


def click(x: int | None = None, y: int | None = None, button: str = "left"):
    """Click at position (or current position if x,y not given)."""
    _ensure_display()
    tool = _get_tool()
    btn_map = {"left": 1, "middle": 2, "right": 3}
    btn = btn_map.get(button, 1)

    if x is not None and y is not None:
        mouse_move(x, y)

    if tool == "xdotool":
        _run(f"xdotool click {btn}")
    else:
        _run(f"ydotool click {btn}")


def double_click(x: int | None = None, y: int | None = None):
    """Double-click at position."""
    _ensure_display()
    if x is not None and y is not None:
        mouse_move(x, y)
    tool = _get_tool()
    if tool == "xdotool":
        _run("xdotool click --repeat 2 --delay 10 1")
    else:
        _run("ydotool click 1")
        import time; time.sleep(0.05)
        _run("ydotool click 1")


def right_click(x: int | None = None, y: int | None = None):
    """Right-click at position."""
    click(x, y, button="right")


def drag(start_x: int, start_y: int, end_x: int, end_y: int):
    """Drag from start to end position."""
    _ensure_display()
    tool = _get_tool()
    if tool == "xdotool":
        _run(f"xdotool mousemove --sync {start_x} {start_y} mousedown 1 mousemove --sync {end_x} {end_y} mouseup 1")
    else:
        mouse_move(start_x, start_y)
        import time
        _run("ydotool click 1")  # down
        time.sleep(0.05)
        mouse_move(end_x, end_y)
        time.sleep(0.05)
        _run("ydotool click 1")  # up


def scroll(direction: str = "down", amount: int = 3, x: int | None = None, y: int | None = None):
    """Scroll in a direction."""
    _ensure_display()
    if x is not None and y is not None:
        mouse_move(x, y)

    tool = _get_tool()
    if tool == "xdotool":
        btn_map = {"up": 4, "down": 5, "left": 6, "right": 7}
        btn = btn_map.get(direction, 5)
        _run(f"xdotool click --repeat {amount} {btn}")
    else:
        # ydotool 0.1.8 doesn't have great scroll support
        btn_map = {"up": 4, "down": 5}
        btn = btn_map.get(direction, 5)
        for _ in range(amount):
            _run(f"ydotool click {btn}")


# === Keyboard Actions ===

def type_text(text: str):
    """Type text with realistic delay."""
    _ensure_display()
    tool = _get_tool()
    for i in range(0, len(text), TYPING_CHUNK_SIZE):
        chunk = text[i:i + TYPING_CHUNK_SIZE]
        if tool == "xdotool":
            _run(f"xdotool type --delay {TYPING_DELAY_MS} -- {shlex.quote(chunk)}")
        else:
            _run(f"ydotool type --key-delay {TYPING_DELAY_MS} -- {shlex.quote(chunk)}")


def press_key(key: str):
    """Press a key or key combination (e.g., 'Return', 'ctrl+c', 'alt+F4')."""
    _ensure_display()
    _run(f"xdotool key -- {key}")


def hotkey(*keys: str):
    """Press a hotkey combination."""
    press_key("+".join(keys))


# === Window Actions ===

def focus_window(name: str | None = None, window_id: int | None = None):
    """Focus a window by name or ID."""
    tool = _get_tool()
    if window_id:
        _run(f"{tool} windowactivate {window_id}")
    elif name:
        _run(f"{tool} search --name {shlex.quote(name)} windowactivate")


def get_active_window() -> dict:
    """Get info about the active window."""
    tool = _get_tool()
    result = _run(f"{tool} getactivewindow getwindowname")
    name = result.stdout.strip()
    result2 = _run(f"{tool} getactivewindow")
    wid = result2.stdout.strip()
    return {"id": wid, "name": name}


def minimize_window():
    _run(f"{_get_tool()} getactivewindow windowminimize")


def maximize_window():
    _run(f"{_get_tool()} key super+Up")


def close_window():
    _run(f"{_get_tool()} key alt+F4")


# === Async Wrappers ===

async def async_click(x=None, y=None, button="left"):
    await asyncio.to_thread(click, x, y, button)

async def async_type_text(text: str):
    await asyncio.to_thread(type_text, text)

async def async_press_key(key: str):
    await asyncio.to_thread(press_key, key)

async def async_scroll(direction="down", amount=3, x=None, y=None):
    await asyncio.to_thread(scroll, direction, amount, x, y)
