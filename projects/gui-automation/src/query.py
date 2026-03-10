#!/usr/bin/env python3
"""AT-SPI quick query - lightweight tool for OpenClaw agent to inspect UI without AI calls."""

import sys
import json
import gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi


def list_apps():
    desktop = Atspi.get_desktop(0)
    apps = []
    for i in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(i)
        if app:
            name = app.get_name() or f"unnamed-{i}"
            windows = []
            for j in range(app.get_child_count()):
                win = app.get_child_at_index(j)
                if win:
                    wname = win.get_name() or ""
                    if wname:
                        windows.append(wname)
            apps.append({"name": name, "windows": windows})
    return apps


def find_clickable(app_name=None, text=None):
    """Find clickable elements, optionally filtered by app and text."""
    desktop = Atspi.get_desktop(0)
    results = []
    clickable_roles = {"push button", "toggle button", "menu item", "link", "check box", "radio button"}

    def search(node, depth=0):
        if depth > 8:
            return
        try:
            role = node.get_role_name() or ""
            name = node.get_name() or ""
            
            if role in clickable_roles:
                if text is None or text.lower() in name.lower():
                    try:
                        rect = node.get_extents(Atspi.CoordType.SCREEN)
                        if rect.width > 0 and rect.height > 0:
                            results.append({
                                "role": role,
                                "name": name,
                                "x": rect.x + rect.width // 2,
                                "y": rect.y + rect.height // 2,
                                "w": rect.width,
                                "h": rect.height,
                            })
                    except:
                        pass

            for i in range(node.get_child_count()):
                child = node.get_child_at_index(i)
                if child:
                    search(child, depth + 1)
        except:
            pass

    for i in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(i)
        if not app:
            continue
        if app_name and (app.get_name() or "").lower() != app_name.lower():
            continue
        search(app)

    return results


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "apps"

    if cmd == "apps":
        for app in list_apps():
            wins = ", ".join(app["windows"][:3]) if app["windows"] else "(no windows)"
            print(f"  {app['name']}: {wins}")

    elif cmd == "find":
        app = sys.argv[2] if len(sys.argv) > 2 else None
        text = sys.argv[3] if len(sys.argv) > 3 else None
        elements = find_clickable(app, text)
        for e in elements[:30]:
            print(f"  [{e['role']}] '{e['name']}' → click({e['x']}, {e['y']})")

    elif cmd == "json":
        app = sys.argv[2] if len(sys.argv) > 2 else None
        text = sys.argv[3] if len(sys.argv) > 3 else None
        print(json.dumps(find_clickable(app, text), ensure_ascii=False, indent=2))

    else:
        print(f"Usage: {sys.argv[0]} apps|find [app_name] [text]|json [app_name] [text]")
