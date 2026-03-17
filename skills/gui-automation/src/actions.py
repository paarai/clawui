"""Actions module - execute mouse, keyboard, and window operations."""

import subprocess
import shlex
import asyncio
import shutil
import logging

logger = logging.getLogger("clawui.actions")
from clawui.exceptions import BackendError, YdotoolError

TYPING_DELAY_MS = 12
TYPING_CHUNK_SIZE = 50

# Mapping from xdotool key names to ydotool KEY_* codes
_YDOTOOL_KEY_MAP = {
    "return": "KEY_ENTER", "Return": "KEY_ENTER", "enter": "KEY_ENTER",
    "tab": "KEY_TAB", "Tab": "KEY_TAB",
    "escape": "KEY_ESC", "Escape": "KEY_ESC",
    "backspace": "KEY_BACKSPACE", "BackSpace": "KEY_BACKSPACE",
    "delete": "KEY_DELETE", "Delete": "KEY_DELETE",
    "space": "KEY_SPACE",
    "up": "KEY_UP", "Up": "KEY_UP",
    "down": "KEY_DOWN", "Down": "KEY_DOWN",
    "left": "KEY_LEFT", "Left": "KEY_LEFT",
    "right": "KEY_RIGHT", "Right": "KEY_RIGHT",
    "home": "KEY_HOME", "Home": "KEY_HOME",
    "end": "KEY_END", "End": "KEY_END",
    "page_up": "KEY_PAGEUP", "Prior": "KEY_PAGEUP",
    "page_down": "KEY_PAGEDOWN", "Next": "KEY_PAGEDOWN",
    "ctrl": "KEY_LEFTCTRL", "Control_L": "KEY_LEFTCTRL",
    "alt": "KEY_LEFTALT", "Alt_L": "KEY_LEFTALT",
    "shift": "KEY_LEFTSHIFT", "Shift_L": "KEY_LEFTSHIFT",
    "super": "KEY_LEFTMETA", "Super_L": "KEY_LEFTMETA",
}
# Add F1-F12
for _i in range(1, 13):
    _YDOTOOL_KEY_MAP[f"F{_i}"] = f"KEY_F{_i}"
# Add letters and digits
for _c in "abcdefghijklmnopqrstuvwxyz":
    _YDOTOOL_KEY_MAP[_c] = f"KEY_{_c.upper()}"
for _d in "0123456789":
    _YDOTOOL_KEY_MAP[_d] = f"KEY_{_d}"


def _xdotool_key_to_ydotool(key: str) -> str:
    """Convert xdotool key combo string to ydotool key format.

    xdotool: 'ctrl+c', 'alt+F4', 'Return'
    ydotool: 'KEY_LEFTCTRL+KEY_C', 'KEY_LEFTALT+KEY_F4', 'KEY_ENTER'
    """
    parts = key.split("+")
    mapped = []
    for part in parts:
        part_stripped = part.strip()
        ydotool_name = _YDOTOOL_KEY_MAP.get(part_stripped)
        if ydotool_name:
            mapped.append(ydotool_name)
        else:
            # Fallback: assume KEY_ prefix for unknown keys
            mapped.append(f"KEY_{part_stripped.upper()}")
    return "+".join(mapped)


def _run(cmd: str, **kwargs) -> subprocess.CompletedProcess:
    """Run a shell command."""
    logger.debug("Running command: %s", cmd)
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        logger.warning("Command failed (%s): %s", result.returncode, cmd)
    return result


def _is_wayland() -> bool:
    import os
    return os.environ.get("XDG_SESSION_TYPE") == "wayland"


def _get_tool() -> str:
    """Select input tool. Prefer xdotool (works via XWayland even on Wayland)."""
    if shutil.which("xdotool"):
        logger.debug("Using input tool: xdotool")
        return "xdotool"
    if shutil.which("ydotool"):
        logger.info("Using ydotool as fallback input backend")
        return "ydotool"
    logger.error("No input tool found (xdotool/ydotool)")
    raise BackendError("No input tool found. Install xdotool or ydotool.")


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
    logger.debug("Click requested: x=%s y=%s button=%s", x, y, button)
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
        import time
        time.sleep(0.05)
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
        _run("ydotool click --down 1")
        time.sleep(0.05)
        mouse_move(end_x, end_y)
        time.sleep(0.05)
        _run("ydotool click --up 1")


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
        # ydotool 1.x uses mousemove --wheel for scrolling
        # Negative = scroll up, positive = scroll down
        delta = amount if direction == "down" else -amount
        _run(f"ydotool mousemove --wheel -- 0 {delta}")


# === Keyboard Actions ===

def type_text(text: str):
    """Type text with realistic delay."""
    logger.debug("Typing text (%d chars)", len(text))
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
    tool = _get_tool()
    if tool == "xdotool":
        _run(f"xdotool key -- {key}")
    else:
        # ydotool uses different key name format; map common combos
        ydotool_key = _xdotool_key_to_ydotool(key)
        _run(f"ydotool key {ydotool_key}")


def hotkey(*keys: str):
    """Press a hotkey combination."""
    press_key("+".join(keys))


# === Window Actions ===

def focus_window(name: str | None = None, window_id: int | None = None):
    """Focus a window by name or ID."""
    logger.info("Focusing window: name=%s window_id=%s", name, window_id)
    if shutil.which("xdotool"):
        if window_id:
            _run(f"xdotool windowactivate {window_id}")
        elif name:
            _run(f"xdotool search --name {shlex.quote(name)} windowactivate")
    elif shutil.which("wmctrl"):
        if window_id:
            _run(f"wmctrl -i -a {window_id}")
        elif name:
            _run(f"wmctrl -a {shlex.quote(name)}")
    else:
        raise BackendError("No window management tool found. Install xdotool or wmctrl.")


def get_active_window() -> dict:
    """Get info about the active window."""
    if shutil.which("xdotool"):
        result = _run("xdotool getactivewindow getwindowname")
        name = result.stdout.strip()
        result2 = _run("xdotool getactivewindow")
        wid = result2.stdout.strip()
        return {"id": wid, "name": name}
    elif shutil.which("xprop"):
        result = _run("xprop -root _NET_ACTIVE_WINDOW")
        wid = result.stdout.strip().split()[-1] if result.stdout.strip() else ""
        return {"id": wid, "name": ""}
    return {"id": "", "name": ""}


def minimize_window():
    if shutil.which("xdotool"):
        _run("xdotool getactivewindow windowminimize")
    else:
        press_key("super+h")  # GNOME minimize shortcut


def maximize_window():
    press_key("super+Up")


def close_window():
    press_key("alt+F4")


# === Clipboard Actions ===

def clipboard_read() -> str:
    """Read text from system clipboard. Tries xclip, then xsel."""
    for tool, args in [("xclip", ["-selection", "clipboard", "-o"]),
                       ("xsel", ["--clipboard", "--output"])]:
        if shutil.which(tool):
            r = subprocess.run([tool] + args, capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                return r.stdout
    raise RuntimeError("No clipboard tool found. Install xclip or xsel.")


def clipboard_write(text: str):
    """Write text to system clipboard. Tries xclip, then xsel."""
    for tool, args in [("xclip", ["-selection", "clipboard"]),
                       ("xsel", ["--clipboard", "--input"])]:
        if shutil.which(tool):
            subprocess.run([tool] + args, input=text, text=True, timeout=5, check=True)
            return
    raise RuntimeError("No clipboard tool found. Install xclip or xsel.")


def clipboard_clear():
    """Clear the system clipboard."""
    try:
        clipboard_write("")
    except RuntimeError:
        raise


# === Async Wrappers ===

async def async_click(x=None, y=None, button="left"):
    await asyncio.to_thread(click, x, y, button)

async def async_type_text(text: str):
    await asyncio.to_thread(type_text, text)

async def async_press_key(key: str):
    await asyncio.to_thread(press_key, key)

async def async_scroll(direction="down", amount=3, x=None, y=None):
    await asyncio.to_thread(scroll, direction, amount, x, y)
