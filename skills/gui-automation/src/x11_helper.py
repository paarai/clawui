"""X11 helper for GUI automation - works with XWayland apps via xdotool/ydotool."""

import subprocess
import re
from dataclasses import dataclass
from typing import List, Tuple, Optional


@dataclass
class X11Window:
    """Represents an X11 window."""
    wid: int
    title: str
    class_name: str
    pid: int
    x: int
    y: int
    width: int
    height: int

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.width // 2, self.y + self.height // 2

    def __str__(self):
        return f"[{self.class_name}] '{self.title}' ({self.wid}x{self.pid}) at ({self.x},{self.y} {self.width}x{self.height})"


def _run_cmd(cmd: List[str]) -> str:
    """Run command and return output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return result.stdout.strip()
    except Exception as e:
        return ""


def _get_window_class(wid: int) -> str:
    """Get window class using xdotool, fallback to xprop."""
    # Try xdotool first
    class_name = _run_cmd(['xdotool', 'getwindowclassname', str(wid)]).strip()
    if class_name:
        return class_name
    # Fallback: xprop WM_CLASS
    try:
        xprop_out = subprocess.run(['xprop', '-id', str(wid), 'WM_CLASS'], capture_output=True, text=True, timeout=2).stdout
        # Output: WM_CLASS(STRING) = "firefox", "Firefox"
        match = re.search(r'=\s*"([^"]+)"\s*,\s*"([^"]+)"', xprop_out)
        if match:
            # Return the second (human-readable) class, or first
            return match.group(2) or match.group(1)
    except:
        pass
    return ""


def list_windows() -> List[X11Window]:
    """List all visible X11 windows with geometry."""
    windows = []
    # Get all window ids
    ids = _run_cmd(['xdotool', 'search', '--onlyvisible', '--name', '']).splitlines()
    for wid in ids:
        try:
            wid_int = int(wid)
            # Get window geometry
            geom = subprocess.run(['xdotool', 'getwindowgeometry', str(wid_int)], capture_output=True, text=True, timeout=2)
            title = _run_cmd(['xdotool', 'getwindowname', str(wid_int)])
            # Use enhanced class detection
            class_name = _get_window_class(wid_int)
            pid_line = _run_cmd(['xdotool', 'getwindowpid', str(wid_int)])
            pid = int(pid_line) if pid_line.isdigit() else 0

            # Parse geometry: "Window 12345:\n  Position: 100,200 (screen: 0)\n  Geometry: 800x600"
            if geom.returncode == 0:
                x, y, w, h = 0, 0, 0, 0
                for line in geom.stdout.splitlines():
                    if 'Position:' in line:
                        # Extract "100,200"
                        pos = re.search(r'Position:\s+(\d+),(\d+)', line)
                        if pos:
                            x, y = int(pos.group(1)), int(pos.group(2))
                    elif 'Geometry:' in line:
                        # Extract "800x600"
                        geo = re.search(r'Geometry:\s+(\d+)x(\d+)', line)
                        if geo:
                            w, h = int(geo.group(1)), int(geo.group(2))

                if w > 0 and h > 0:
                    windows.append(X11Window(
                        wid=wid_int,
                        title=title or "",
                        class_name=class_name or "",
                        pid=pid,
                        x=x, y=y, width=w, height=h
                    ))
        except Exception:
            continue
    return windows


def find_windows_by_class(class_name: str) -> List[X11Window]:
    """Find windows matching class name (case-insensitive)."""
    return [w for w in list_windows() if class_name.lower() in w.class_name.lower()]


def find_windows_by_title(title: str) -> List[X11Window]:
    """Find windows matching title (case-insensitive)."""
    return [w for w in list_windows() if title.lower() in w.title.lower()]


def activate_window(wid: int):
    """Bring window to front."""
    _run_cmd(['xdotool', 'windowactivate', '--sync', str(wid)])


def click_at(x: int, y: int, button: int = 1):
    """Click at absolute screen coordinates."""
    _run_cmd(['xdotool', 'mousemove', str(x), str(y), 'click', str(button)])


def click_window(wid: int, button: int = 1):
    """Click center of window."""
    windows = [w for w in list_windows() if w.wid == wid]
    if windows:
        w = windows[0]
        click_at(w.x + w.width // 2, w.y + w.height // 2, button)


def type_text(text: str):
    """Type text using keyboard."""
    _run_cmd(['xdotool', 'type', '--delay', '50', text])


def key_press(keysym: str):
    """Press a key (e.g., 'Return', 'Tab', 'ctrl+l')."""
    _run_cmd(['xdotool', 'key', keysym])


def get_window_tree(max_depth: int = 5) -> str:
    """Get a tree representation of all windows (similar to atspi tree output)."""
    lines = []
    windows = list_windows()

    # Group by class
    classes = {}
    for w in windows:
        cls = w.class_name or "unknown"
        if cls not in classes:
            classes[cls] = []
        classes[cls].append(w)

    for cls, wins in classes.items():
        lines.append(f"📱 {cls}")
        for w in wins[:10]:  # limit per class
            title_short = (w.title[:40] + '...') if len(w.title) > 40 else w.title
            lines.append(f"  [window] '{title_short}' (wid={w.wid}, pid={w.pid})")
        if len(wins) > 10:
            lines.append(f"  ... and {len(wins)-10} more")
        lines.append("")

    return "\n".join(lines) if lines else "No X11 windows found"


def get_ui_tree_summary(app_name: Optional[str] = None, max_depth: int = 5) -> Tuple[str, List[X11Window]]:
    """Get UI tree summary, optionally filtered by app name."""
    windows = list_windows()
    if app_name:
        windows = [w for w in windows if app_name.lower() in w.class_name.lower() or app_name.lower() in w.title.lower()]

    summary_lines = []
    for w in windows[:50]:  # limit
        title_display = w.title[:30] if w.title else "(no title)"
        summary_lines.append(f"📱 {w.class_name}: '{title_display}' - {w.width}x{w.height} at ({w.x},{w.y})")
    summary = "\n".join(summary_lines) if summary_lines else "No matching windows"
    return summary, windows


# Backward compatibility: keep old function signatures
def list_applications() -> List[str]:
    """Return unique class names of all visible windows."""
    windows = list_windows()
    classes = sorted(set(w.class_name for w in windows if w.class_name))
    return classes


def do_action(wid: int, action_name: str, value=None):
    """Perform an action on a window (limited by xdotool capabilities)."""
    if action_name == "click":
        click_window(wid)
    elif action_name == "activate":
        activate_window(wid)
    elif action_name == "type":
        if value:
            activate_window(wid)
            type_text(value)
    # Cannot implement semantic actions without UI tree
    else:
        raise NotImplementedError(f"x11 backend does not support action: {action_name}")


def set_text(wid: int, text: str):
    """Set window text (basic implementation)."""
    activate_window(wid)
    type_text(text)


def find_elements(role=None, name=None):
    """Find elements - limited to window-level matching."""
    windows = list_windows()
    results = []
    for w in windows:
        if role and role not in w.class_name.lower():
            continue
        if name and name.lower() not in w.title.lower():
            continue
        results.append(w)
    return results
