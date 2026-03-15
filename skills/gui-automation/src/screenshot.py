"""Screenshot module - capture and process screen images.

Supports X11 (scrot) and Wayland (GNOME D-Bus portal / grim).
"""

import logging

logger = logging.getLogger("clawui.screenshot")

import base64
import json
import os
import shutil
import subprocess
import asyncio
import time
import logging

logger = logging.getLogger("clawui.screenshot")
from pathlib import Path
from uuid import uuid4

OUTPUT_DIR = Path("/tmp/gui-automation-screenshots")

# Max resolution targets for AI processing
MAX_RESOLUTIONS = {
    "XGA": (1024, 768),
    "WXGA": (1280, 800),
    "FWXGA": (1366, 768),
}


def _get_session_type() -> str:
    """Detect wayland vs x11."""
    return os.environ.get("XDG_SESSION_TYPE", "x11")


def _dbus_env() -> dict:
    """Build env dict with D-Bus session address."""
    env = os.environ.copy()
    uid = os.getuid()
    bus = f"unix:path=/run/user/{uid}/bus"
    env.setdefault("DBUS_SESSION_BUS_ADDRESS", bus)
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{uid}")
    env.setdefault("WAYLAND_DISPLAY", "wayland-0")
    return env


def _gnome_dbus_screenshot(path: str) -> bool:
    """Take screenshot via GNOME Shell D-Bus (works under Wayland)."""
    env = _dbus_env()
    try:
        # Try org.gnome.Shell.Screenshot first
        r = subprocess.run(
            ["gdbus", "call", "--session",
             "--dest", "org.gnome.Shell.Screenshot",
             "--object-path", "/org/gnome/Shell/Screenshot",
             "--method", "org.gnome.Shell.Screenshot.Screenshot",
             "false", "true", path],
            capture_output=True, text=True, env=env, timeout=10,
        )
        if r.returncode == 0:
            return True
    except Exception:
        pass

    # Fallback: Portal-based screenshot (interactive, may show dialog)
    try:
        r = subprocess.run(
            ["gdbus", "call", "--session",
             "--dest", "org.freedesktop.portal.Desktop",
             "--object-path", "/org/freedesktop/portal/desktop",
             "--method", "org.freedesktop.portal.Screenshot.Screenshot",
             "", "{}"],
            capture_output=True, text=True, env=env, timeout=15,
        )
        if r.returncode == 0:
            # Portal saves to a temp file; need to find it
            # Wait a moment for portal to process
            time.sleep(1)
            # Check common portal output locations
            for candidate in Path("/tmp").glob("screenshot*.png"):
                if candidate.stat().st_mtime > time.time() - 5:
                    shutil.move(str(candidate), path)
                    return True
    except Exception:
        pass
    return False


def _kscreen_screenshot(path: str) -> bool:
    """Take screenshot via spectacle (KDE) CLI."""
    try:
        r = subprocess.run(
            ["spectacle", "-b", "-n", "-o", path],
            capture_output=True, timeout=10, env=_dbus_env(),
        )
        return r.returncode == 0
    except Exception:
        return False


def get_screen_size() -> tuple[int, int]:
    """Get current screen resolution."""
    # Wayland: try wlr-randr or gnome-randr
    if _get_session_type() == "wayland":
        try:
            env = _dbus_env()
            output = subprocess.check_output(
                ["xrandr", "--current"], stderr=subprocess.DEVNULL, env=env
            ).decode()
            for line in output.split("\n"):
                if "*" in line:
                    parts = line.strip().split()
                    w, h = parts[0].split("x")
                    return int(w), int(h)
        except Exception as e:
            logger.warning("Screenshot scaling failed: %s", e)
            pass

    try:
        output = subprocess.check_output(
            ["xdpyinfo"], stderr=subprocess.DEVNULL
        ).decode()
        for line in output.split("\n"):
            if "dimensions:" in line:
                size = line.split()[1]
                w, h = size.split("x")
                return int(w), int(h)
    except Exception:
        pass
    # Fallback: try xrandr
    try:
        output = subprocess.check_output(
            ["xrandr", "--current"], stderr=subprocess.DEVNULL
        ).decode()
        for line in output.split("\n"):
            if "*" in line:
                parts = line.strip().split()
                w, h = parts[0].split("x")
                return int(w), int(h)
    except Exception:
        pass
    return 1920, 1080  # Default fallback


def _select_target_resolution(width: int, height: int) -> tuple[int, int] | None:
    """Select appropriate target resolution for scaling."""
    ratio = width / height
    for tw, th in MAX_RESOLUTIONS.values():
        if abs(tw / th - ratio) < 0.02 and tw < width:
            return tw, th
    return None


def take_screenshot(
    region: tuple[int, int, int, int] | None = None,
    window_name: str | None = None,
    scale: bool = True,
) -> str:
    """
    Take a screenshot and return base64-encoded PNG.
    
    Args:
        region: Optional (x, y, width, height) to capture a specific area
        window_name: Optional app/window name to capture just that window
                     (uses AT-SPI to find geometry; fallback to full screen)
        scale: Whether to scale down large screenshots
    
    Returns:
        Base64-encoded PNG string
    """
    # If window_name given, try to locate its geometry via AT-SPI
    if window_name and not region:
        try:
            from .atspi_helper import find_elements
            # Find the main application window or frame matching the name
            candidates = find_elements(role="frame", name=window_name)
            if not candidates:
                # Try partial match
                for role in ["frame", "window", "application"]:
                    candidates = find_elements(role=role)
                    for c in candidates:
                        if window_name.lower() in (c.name or "").lower():
                            candidates = [c]
                            break
                    if candidates:
                        break
            if candidates:
                el = candidates[0]
                # Get geometry: position (x,y) and size (width,height)
                # AT-SPI elements have .position and .size or .extents
                if hasattr(el, 'position') and hasattr(el, 'size'):
                    x, y = el.position
                    w, h = el.size
                    region = (x, y, w, h)
                elif hasattr(el, 'extents'):
                    x1, y1, x2, y2 = el.extents  # or (x, y, width, height)?
                    # Need to check format - usually (x, y, width, height) or (x1,y1,x2,y2)
                    # Let's be safe: if extents has 4 values, assume (x,y,w,h)
                    if len(el.extents) == 4:
                        region = el.extents
        except Exception as e:
            logger.warning("Window lookup failed for %s: %s", window_name, e)
            region = None

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"screenshot_{uuid4().hex}.png"
    spath = str(path)
    session_type = _get_session_type()
    logger.info("Taking screenshot session_type=%s region=%s window_name=%s scale=%s", session_type, region, window_name, scale)
    captured = False
    captured_fullscreen = False

    if region:
        x, y, w, h = region
        # On X11 we can capture region directly via scrot.
        if session_type != "wayland" and shutil.which("scrot"):
            subprocess.run(
                ["scrot", "-a", f"{x},{y},{w},{h}", spath],
                check=True, capture_output=True,
            )
            captured = Path(spath).exists()
            captured_fullscreen = False
        else:
            # Wayland (or missing scrot): capture full screen first, then crop.
            captured = False

    if not captured:
        # Full screen capture chain (Wayland or X11)
        # Same as original - pick the method that works
        if session_type == "wayland":
            # Wayland: gnome-screenshot (works via XWayland), then grim, then D-Bus portal
            if shutil.which("gnome-screenshot"):
                try:
                    env = _dbus_env()
                    env["DISPLAY"] = ":0"
                    subprocess.run(
                        ["gnome-screenshot", "-f", spath],
                        check=True, capture_output=True, env=env, timeout=10,
                    )
                    if Path(spath).exists() and Path(spath).stat().st_size > 0:
                        captured = True
                        captured_fullscreen = True
                except Exception as e:
                    logger.debug("gnome-screenshot failed: %s", e)
                    pass
            if not captured and shutil.which("grim"):
                try:
                    subprocess.run(
                        ["grim", spath],
                        check=True, capture_output=True, env=_dbus_env(),
                    )
                    captured = True
                    captured_fullscreen = True
                except Exception as e:
                    logger.debug("grim failed: %s", e)
                    pass
            if not captured:
                captured = _gnome_dbus_screenshot(spath)
                if captured:
                    captured_fullscreen = True
            if not captured:
                captured = _kscreen_screenshot(spath)
                if captured:
                    captured_fullscreen = True
        else:
            # X11 fallback chain
            for cmd in [
                ["gnome-screenshot", "-f", spath, "-p"],
                ["scrot", "-p", spath],
                ["grim", spath],
            ]:
                if shutil.which(cmd[0]):
                    try:
                        subprocess.run(cmd, check=True, capture_output=True)
                        captured = True
                        captured_fullscreen = True
                        logger.debug("Captured screenshot with %s", cmd[0])
                        break
                    except Exception as e:
                        logger.debug("Screenshot method %s failed: %s", cmd[0], e)
                        continue

        if not captured:
            logger.error("No screenshot method worked")
            raise RuntimeError("No screenshot method worked. Tried GNOME D-Bus, grim, scrot, gnome-screenshot.")

    # If we captured full screen but wanted a region, crop it now
    # Crop only when region was requested and we captured a full-screen image.
    # If region was captured directly via scrot -a, cropping again would be wrong.
    if region and captured and captured_fullscreen:
        from PIL import Image
        img = Image.open(spath)
        # Crop to region (x,y,w,h) from the full screenshot
        x, y, w, h = region
        cropped = img.crop((x, y, x + w, y + h))
        cropped.save(spath)

    if scale and shutil.which("convert"):
        try:
            screen_w, screen_h = get_screen_size()
            target = _select_target_resolution(screen_w, screen_h)
            if target:
                tw, th = target
                subprocess.run(
                    ["convert", str(path), "-resize", f"{tw}x{th}!", str(path)],
                    check=True, capture_output=True,
                )
                logger.debug("Scaled screenshot to %sx%s", tw, th)
        except Exception:
            pass

    if path.exists():
        data = base64.b64encode(path.read_bytes()).decode()
        logger.debug("Screenshot captured successfully: %s", spath)
        path.unlink(missing_ok=True)
        return data

    logger.error("Failed to take screenshot: output file missing")
    raise RuntimeError("Failed to take screenshot")


async def take_screenshot_async(**kwargs) -> str:
    """Async wrapper for take_screenshot."""
    return await asyncio.to_thread(take_screenshot, **kwargs)
