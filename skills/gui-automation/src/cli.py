#!/usr/bin/env python3
"""ClawUI CLI - AI-driven GUI automation for Linux.

Usage examples:
    clawui run "Open Firefox and search for cats"
    clawui apps
    clawui tree --app Firefox
    clawui screenshot -o screen.png
    clawui elements
    clawui find "OK"
    clawui click --text "OK"
    clawui click --coords 100,200
    clawui inspect
    clawui inspect --app Firefox --ocr --save screen.png
    clawui record demo
    clawui replay recordings/demo.json
    clawui export recordings/demo.json -o demo.py
    clawui browser https://example.com
    clawui type "hello"
    clawui key "ctrl+c"
"""

import argparse
import base64
import os
import subprocess
import sys
import time

VERSION = "0.7.0"


def _import_error(module_name: str, exc: Exception) -> int:
    print(f"Error: required module '{module_name}' is unavailable: {exc}", file=sys.stderr)
    print("Tip: check optional dependencies and your environment setup.", file=sys.stderr)
    return 2


def _runtime_error(action: str, exc: Exception) -> int:
    print(f"Error while running '{action}': {exc}", file=sys.stderr)
    return 1


def _run_inspect(args) -> int:
    """Analyze current screen: screenshot + interactive elements + optional OCR."""
    import json as json_mod
    import time
    results = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "elements": [], "ocr_lines": [], "apps": []}

    # 1. List applications
    try:
        from .perception import list_applications
        apps = list_applications()
        if isinstance(apps, list):
            results["apps"] = apps
        elif isinstance(apps, str):
            results["apps"] = [line.strip() for line in apps.strip().split("\n") if line.strip()]
    except Exception as e:
        results["apps_error"] = str(e)

    # 2. Get interactive elements
    try:
        from .atspi_helper import find_elements
        roles = ["push button", "toggle button", "menu item", "text", "check box",
                 "radio button", "combo box", "link", "entry", "spin button"]
        elements = []
        app_filter = args.app if hasattr(args, 'app') and args.app else None
        for role in roles:
            try:
                found = find_elements(role=role, app_name=app_filter)
                if isinstance(found, list):
                    for el in found[:20]:
                        if hasattr(el, 'name') and el.name:
                            elements.append({
                                "role": role, "name": el.name,
                                "x": getattr(el, 'x', None), "y": getattr(el, 'y', None),
                            })
                        elif isinstance(el, dict):
                            elements.append(el)
            except Exception:
                pass
        results["elements"] = elements[:200]
    except ImportError:
        results["elements_error"] = "AT-SPI not available"

    # 3. Screenshot
    try:
        from .screenshot import take_screenshot
        img_b64 = take_screenshot()
        if img_b64:
            if hasattr(args, 'save') and args.save:
                import base64 as b64mod
                with open(args.save, 'wb') as f:
                    f.write(b64mod.b64decode(img_b64))
                results["screenshot"] = f"saved:{args.save}"
            else:
                results["screenshot"] = f"captured ({len(img_b64)} chars base64)"
    except Exception as e:
        results["screenshot_error"] = str(e)

    # 4. Optional OCR
    if hasattr(args, 'ocr') and args.ocr:
        try:
            from .ocr_tool import ocr_extract_lines
            lines = ocr_extract_lines()
            if isinstance(lines, list):
                results["ocr_lines"] = [l if isinstance(l, str) else str(l) for l in lines[:100]]
            elif isinstance(lines, str):
                results["ocr_lines"] = lines.strip().split("\n")[:100]
        except Exception as e:
            results["ocr_error"] = str(e)

    # 5. CDP browser state
    try:
        from .cdp_helper import get_or_create_cdp_client
        client = get_or_create_cdp_client()
        if client:
            tabs = client.list_tabs() if hasattr(client, 'list_tabs') else []
            results["browser"] = {"connected": True, "tabs": len(tabs) if isinstance(tabs, list) else 0}
    except Exception:
        results["browser"] = {"connected": False}

    # Output
    if hasattr(args, 'json_output') and args.json_output:
        print(json_mod.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(f"🔍 ClawUI Screen Inspection — {results['timestamp']}")
        print("=" * 55)
        apps = results.get("apps", [])
        if apps:
            print(f"\n📱 Running Applications ({len(apps)}):")
            for app in apps[:15]:
                print(f"   • {app}")
            if len(apps) > 15:
                print(f"   ... and {len(apps) - 15} more")
        elements = results.get("elements", [])
        if elements:
            print(f"\n🎯 Interactive Elements ({len(elements)}):")
            for i, el in enumerate(elements[:30]):
                name = el.get("name", "?")
                role = el.get("role", "?")
                coords = ""
                if el.get("x") is not None and el.get("y") is not None:
                    coords = f" @ ({el['x']}, {el['y']})"
                print(f"   [{i+1:2d}] {role}: {name}{coords}")
            if len(elements) > 30:
                print(f"   ... and {len(elements) - 30} more")
        if results.get("screenshot"):
            print(f"\n📸 Screenshot: {results['screenshot']}")
        elif results.get("screenshot_error"):
            print(f"\n📸 Screenshot: ❌ {results['screenshot_error']}")
        ocr_lines = results.get("ocr_lines", [])
        if ocr_lines:
            print(f"\n📝 OCR Text ({len(ocr_lines)} lines):")
            for line in ocr_lines[:20]:
                print(f"   {line}")
            if len(ocr_lines) > 20:
                print(f"   ... and {len(ocr_lines) - 20} more lines")
        browser = results.get("browser", {})
        if browser.get("connected"):
            print(f"\n🌐 Browser: Connected ({browser.get('tabs', 0)} tabs)")
        else:
            print("\n🌐 Browser: Not connected")
        print(f"\nTotal: {len(apps)} apps, {len(elements)} elements" +
              (f", {len(ocr_lines)} OCR lines" if ocr_lines else ""))
    return 0


def _run_doctor() -> int:
    """Run environment diagnostics and report status of all backends."""
    import shutil

    print(f"ClawUI Doctor v{VERSION}")
    print("=" * 50)
    issues = []

    # 1. Display server
    print("\n🖥️  Display Server")
    session_type = os.environ.get("XDG_SESSION_TYPE", "unknown")
    display = os.environ.get("DISPLAY", "")
    wayland = os.environ.get("WAYLAND_DISPLAY", "")
    print(f"  Session type: {session_type}")
    print(f"  DISPLAY: {display or '(not set)'}")
    print(f"  WAYLAND_DISPLAY: {wayland or '(not set)'}")
    if not display and not wayland:
        issues.append("No display server detected (DISPLAY and WAYLAND_DISPLAY both unset)")

    # 2. AT-SPI (accessibility)
    print("\n♿ AT-SPI (Accessibility)")
    try:
        import gi
        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi
        desktop = Atspi.get_desktop(0)
        n_apps = desktop.get_child_count()
        print(f"  ✅ AT-SPI available ({n_apps} apps detected)")
    except Exception as e:
        print(f"  ❌ AT-SPI unavailable: {e}")
        issues.append("AT-SPI not available — install python3-gi and at-spi2-core")

    # 3. X11 tools
    print("\n🪟 X11 Tools")
    for tool in ["xdotool", "xwininfo", "xprop"]:
        path = shutil.which(tool)
        if path:
            print(f"  ✅ {tool}: {path}")
        else:
            print(f"  ❌ {tool}: not found")
            issues.append(f"{tool} not found — install xdotool / x11-utils")

    # 4. Screenshot tools
    print("\n📸 Screenshot")
    for tool in ["grim", "gnome-screenshot", "scrot", "import"]:
        path = shutil.which(tool)
        if path:
            print(f"  ✅ {tool}: {path}")
            break
    else:
        print("  ❌ No screenshot tool found")
        issues.append("No screenshot tool found — install grim (Wayland) or scrot (X11)")

    # 5. OCR
    print("\n🔍 OCR (Tesseract)")
    tess = shutil.which("tesseract")
    if tess:
        try:
            langs = subprocess.check_output(["tesseract", "--list-langs"], stderr=subprocess.STDOUT).decode()
            lang_list = [l.strip() for l in langs.strip().split("\n")[1:] if l.strip()]
            print(f"  ✅ tesseract: {tess} ({len(lang_list)} languages: {', '.join(lang_list[:5])}{'...' if len(lang_list) > 5 else ''})")
        except Exception:
            print(f"  ✅ tesseract: {tess}")
    else:
        print("  ⚠️  tesseract not found — OCR features will be limited")
        issues.append("tesseract not found — install tesseract-ocr for OCR features")

    # 6. CDP (Chromium DevTools Protocol)
    print("\n🌐 CDP (Browser Automation)")
    try:
        from .cdp_helper import get_or_create_cdp_client
        client = get_or_create_cdp_client()
        if client and client.is_available():
            title = client.get_page_title() or "(no title)"
            print(f"  ✅ CDP connected — current page: {title}")
        else:
            print("  ⚠️  CDP not connected (start Chromium with --remote-debugging-port=9222)")
    except Exception as e:
        print(f"  ⚠️  CDP unavailable: {e}")

    # 7. Firefox Marionette
    print("\n🦊 Firefox Marionette")
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex(("127.0.0.1", 2828))
        s.close()
        if result == 0:
            print("  ✅ Marionette port 2828 is open")
        else:
            print("  ⚠️  Marionette not connected (start Firefox with --marionette)")
    except Exception:
        print("  ⚠️  Could not check Marionette port")

    # 8. Python dependencies
    print("\n🐍 Python Dependencies")
    deps = {
        "PIL": "Pillow (image processing)",
        "numpy": "NumPy (annotated screenshots)",
        "pytesseract": "pytesseract (OCR wrapper)",
        "websocket": "websocket-client (CDP)",
    }
    for mod, desc in deps.items():
        try:
            __import__(mod)
            print(f"  ✅ {desc}")
        except ImportError:
            print(f"  ❌ {desc} — not installed")
            issues.append(f"Missing Python package: {desc}")

    # Summary
    print("\n" + "=" * 50)
    if issues:
        print(f"⚠️  {len(issues)} issue(s) found:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        return 1
    else:
        print("✅ All checks passed — ClawUI is ready!")
        return 0


def _parse_coords(coords: str) -> tuple[int, int]:
    parts = [p.strip() for p in coords.split(",")]
    if len(parts) != 2:
        raise ValueError("coords must be in format x,y")
    return int(parts[0]), int(parts[1])


def _run_wait(args) -> int:
    deadline = time.time() + max(0.1, float(args.timeout))
    interval = max(0.05, float(args.interval))

    if args.text:
        from .screenshot import take_screenshot
        from .ocr_tool import ocr_find_text

        while time.time() < deadline:
            matches = ocr_find_text(take_screenshot(), args.text)
            if matches:
                best = sorted(matches, key=lambda m: m.get("score", 0), reverse=True)[0]
                cx, cy = best.get("center", [None, None])
                print(f"Found text '{best.get('text', args.text)}' at ({cx}, {cy})")
                return 0
            time.sleep(interval)

        print(f"Timeout waiting for text: {args.text}", file=sys.stderr)
        return 1

    from .atspi_helper import find_elements

    role = None
    name = args.element
    if ":" in args.element:
        role, name = [x.strip() for x in args.element.split(":", 1)]

    while time.time() < deadline:
        found = find_elements(name=name, role=role)
        if found:
            print(f"Found element: {args.element} ({len(found)} match(es))")
            return 0
        time.sleep(interval)

    print(f"Timeout waiting for element: {args.element}", file=sys.stderr)
    return 1


def _run_selftest(args) -> int:
    """Run end-to-end self-test validating the full automation pipeline."""
    import tempfile
    import shutil

    print(f"ClawUI Self-Test v{VERSION}")
    print("=" * 50)

    passed = 0
    failed = 0
    total = 0
    tmpdir = tempfile.mkdtemp(prefix="clawui_selftest_")

    def _test(name: str, fn) -> bool:
        nonlocal passed, failed, total
        total += 1
        try:
            result = fn()
            if result:
                print(f"  ✅ {name}")
                passed += 1
                return True
            else:
                print(f"  ❌ {name}: returned falsy")
                failed += 1
                return False
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            failed += 1
            return False

    # 1. Screenshot
    print("\n📸 Screenshot Pipeline")
    screenshot_path = os.path.join(tmpdir, "selftest_screen.png")

    def test_screenshot():
        from .screenshot import take_screenshot
        img = take_screenshot()
        if img:
            img.save(screenshot_path)
            size = os.path.getsize(screenshot_path)
            print(f"      Saved {size:,} bytes → {screenshot_path}")
            return size > 0
        return False
    _test("Take screenshot", test_screenshot)

    # 2. OCR
    print("\n🔍 OCR Pipeline")

    def test_ocr():
        from .ocr_tool import ocr_screenshot
        results = ocr_screenshot()
        count = len(results) if isinstance(results, list) else 0
        print(f"      Detected {count} text regions")
        return True  # OCR finding nothing is OK (headless, etc.)
    _test("OCR text detection", test_ocr)

    # 3. AT-SPI (accessibility)
    print("\n♿ AT-SPI Element Detection")

    def test_atspi():
        from .perception import list_applications
        apps = list_applications()
        if isinstance(apps, list):
            print(f"      Found {len(apps)} applications")
            return True
        return bool(apps)
    _test("List applications", test_atspi)

    def test_atspi_tree():
        from .perception import find_elements
        elems = find_elements()
        count = len(elems) if isinstance(elems, list) else 0
        print(f"      Found {count} interactive elements")
        return True  # 0 elements is OK in headless
    _test("Find interactive elements", test_atspi_tree)

    # 4. Annotated screenshot (Set-of-Mark)
    print("\n🏷️  Annotated Screenshot")

    def test_annotate():
        from .annotated_screenshot import annotated_screenshot
        b64, labeled = annotated_screenshot()
        ann_path = os.path.join(tmpdir, "selftest_annotated.png")
        import base64 as b64_mod
        raw = b64_mod.b64decode(b64)
        with open(ann_path, 'wb') as f:
            f.write(raw)
        print(f"      {len(labeled)} elements labeled, saved → {ann_path}")
        return len(raw) > 0
    _test("Generate annotated screenshot", test_annotate)

    # 5. Browser (CDP) — skip with --quick
    if not getattr(args, 'quick', False):
        print("\n🌐 Browser Automation (CDP)")

        cdp_client = None

        def test_cdp_connect():
            nonlocal cdp_client
            from .cdp_helper import get_or_create_cdp_client
            cdp_client = get_or_create_cdp_client()
            if cdp_client and cdp_client.is_available():
                print(f"      Connected to CDP")
                return True
            print(f"      CDP not available (Chromium not running or auto-launch failed)")
            return False

        if _test("CDP connect/auto-launch", test_cdp_connect) and cdp_client:
            def test_navigate():
                cdp_client.navigate("data:text/html,<h1>ClawUI Self-Test</h1><p>If you can read this, CDP works!</p><button id='btn'>Click Me</button>")
                time.sleep(0.5)
                title = cdp_client.get_page_title()
                print(f"      Page title: {title}")
                return True
            _test("Navigate to test page", test_navigate)

            def test_cdp_js():
                result = cdp_client.evaluate_js("document.querySelector('h1').textContent")
                print(f"      JS eval result: {result}")
                return result and "ClawUI" in str(result)
            _test("JavaScript evaluation", test_cdp_js)

            def test_cdp_screenshot():
                ss_path = os.path.join(tmpdir, "selftest_cdp.png")
                b64data = cdp_client.screenshot()
                if b64data:
                    import base64 as b64_mod
                    raw = b64_mod.b64decode(b64data) if isinstance(b64data, str) else b64data
                    with open(ss_path, 'wb') as f:
                        f.write(raw)
                    print(f"      Browser screenshot saved → {ss_path}")
                    return len(raw) > 0
                return False
            _test("Browser screenshot", test_cdp_screenshot)

            def test_cdp_click():
                cdp_client.evaluate_js("document.getElementById('btn').addEventListener('click', () => { document.title = 'Clicked!'; })")
                cdp_client.evaluate_js("document.getElementById('btn').click()")
                time.sleep(0.3)
                title = cdp_client.get_page_title()
                print(f"      After click, title: {title}")
                return title == "Clicked!"
            _test("Browser click simulation", test_cdp_click)
    else:
        print("\n🌐 Browser tests skipped (--quick)")

    # Summary
    print("\n" + "=" * 50)
    if failed == 0:
        print(f"✅ All {passed}/{total} tests passed!")
    else:
        print(f"⚠️  {passed}/{total} passed, {failed} failed")

    if not getattr(args, 'keep', False):
        shutil.rmtree(tmpdir, ignore_errors=True)
        print(f"🧹 Cleaned up temp files")
    else:
        print(f"📁 Temp files kept at: {tmpdir}")

    return 0 if failed == 0 else 1


def main():
    parser = argparse.ArgumentParser(
        prog="clawui",
        description="AI-driven GUI automation for Linux desktop and browser",
    )
    subparsers = parser.add_subparsers(dest="command")

    # Run a task
    run_p = subparsers.add_parser("run", help="Run a GUI automation task")
    run_p.add_argument("task", help="Task description in natural language")
    run_p.add_argument("--model", default="claude-sonnet-4-20250514", help="AI model to use")
    run_p.add_argument("--max-steps", type=int, default=30, help="Maximum agent steps")
    run_p.add_argument("--log", help="Write structured JSON run log to file (for debugging/replay analysis)")

    # List apps
    subparsers.add_parser("apps", help="List running applications (AT-SPI + X11)")

    # UI tree
    tree_p = subparsers.add_parser("tree", help="Show UI element tree")
    tree_p.add_argument("--app", help="Filter by application name")
    tree_p.add_argument("--depth", type=int, default=5, help="Maximum tree depth")

    # Screenshot
    screen_p = subparsers.add_parser("screenshot", help="Take a screenshot")
    screen_p.add_argument("-o", "--output", help="Save to file (PNG)")

    # Elements (annotated_screenshot in text mode)
    elements_p = subparsers.add_parser("elements", help="List interactive elements currently on screen")
    elements_p.add_argument(
        "--source",
        choices=["auto", "atspi", "cdp"],
        default="auto",
        help="Element source: desktop (atspi), browser (cdp), or both (auto)",
    )
    elements_p.add_argument("--max", type=int, default=80, help="Maximum elements to list")

    # OCR find
    find_p = subparsers.add_parser("find", help="Find text on screen using OCR")
    find_p.add_argument("text", help="Text to find (case-insensitive partial match)")

    # Click
    click_p = subparsers.add_parser("click", help="Click by OCR text match or explicit coordinates")
    group = click_p.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Text to find on screen via OCR and click")
    group.add_argument("--coords", help="Coordinates in format x,y (example: 100,200)")

    # Record/replay
    record_p = subparsers.add_parser("record", help="Start recording actions to recordings/NAME.json")
    record_p.add_argument("name", help="Recording name")

    replay_p = subparsers.add_parser("replay", help="Replay actions from a recording JSON file")
    replay_p.add_argument("file", help="Path to recording JSON file")
    replay_p.add_argument("--speed", type=float, default=1.0, help="Playback speed multiplier")
    replay_p.add_argument("--dry-run", action="store_true", help="Preview without executing")

    export_p = subparsers.add_parser("export", help="Export recording JSON to standalone Python script")
    export_p.add_argument("file", help="Path to recording JSON file")
    export_p.add_argument("-o", "--output", help="Output Python script path (default: same name with .py)")
    export_p.add_argument("--speed", type=float, default=1.0, help="Playback speed multiplier for generated sleep delays")

    # Browser
    browser_p = subparsers.add_parser("browser", help="Navigate Chromium/Chrome to URL via CDP")
    browser_p.add_argument("url", help="URL to open")

    # Type/key
    type_p = subparsers.add_parser("type", help="Type text with keyboard simulation")
    type_p.add_argument("text", help="Text to type")

    key_p = subparsers.add_parser("key", help="Press a key or key combo (example: ctrl+c)")
    key_p.add_argument("combo", help="Key or combo to press")

    # Test
    test_p = subparsers.add_parser("test", help="Run unit tests (pytest tests/)")
    test_p.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    # Inspect (combined screen analysis)
    inspect_p = subparsers.add_parser("inspect", help="Analyze current screen: screenshot + OCR + elements")
    inspect_p.add_argument("--app", help="Focus on specific application")
    inspect_p.add_argument("--save", help="Save annotated screenshot to file")
    inspect_p.add_argument("--ocr", action="store_true", help="Include OCR text extraction")
    inspect_p.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")

    # Wait (element/text appearance)
    wait_p = subparsers.add_parser("wait", help="Wait for element or text to appear on screen")
    wait_group = wait_p.add_mutually_exclusive_group(required=True)
    wait_group.add_argument("--text", help="Wait for text to appear (OCR-based)")
    wait_group.add_argument("--element", help="Wait for AT-SPI element by name/role (format: role:name or just name)")
    wait_p.add_argument("--timeout", type=float, default=10.0, help="Timeout in seconds (default: 10)")
    wait_p.add_argument("--interval", type=float, default=0.5, help="Poll interval in seconds (default: 0.5)")

    # Doctor (diagnostics)
    subparsers.add_parser("doctor", help="Check environment and diagnose issues")

    # Annotate
    annotate_p = subparsers.add_parser("annotate", help="Take annotated screenshot with numbered element labels (Set-of-Mark)")
    annotate_p.add_argument("-o", "--output", default="annotated.png", help="Output file path (default: annotated.png)")
    annotate_p.add_argument("--source", choices=["auto", "atspi", "cdp", "both"], default="auto", help="Element detection source")
    annotate_p.add_argument("--json", dest="json_output", action="store_true", help="Output element list as JSON")

    # Selftest (end-to-end validation)
    selftest_p = subparsers.add_parser("selftest", help="Run end-to-end self-test: screenshot, OCR, browser automation")
    selftest_p.add_argument("--quick", action="store_true", help="Skip browser tests (desktop-only)")
    selftest_p.add_argument("--keep", action="store_true", help="Keep temporary files after test")

    # Version
    subparsers.add_parser("version", help="Show version")

    args = parser.parse_args()

    if args.command == "run":
        try:
            from .agent import run_agent
        except ImportError as e:
            return _import_error("agent", e)
        try:
            result = run_agent(args.task, max_steps=args.max_steps, model=args.model,
                               log_file=getattr(args, 'log', None))
            print(f"\nResult: {result}")
            return 0
        except Exception as e:
            return _runtime_error("run", e)

    elif args.command == "apps":
        try:
            from .perception import list_applications
        except ImportError as e:
            return _import_error("perception", e)
        try:
            apps = list_applications()
            if isinstance(apps, list):
                for app in apps:
                    print(f"  • {app}")
            else:
                print(apps)
            return 0
        except Exception as e:
            return _runtime_error("apps", e)

    elif args.command == "tree":
        try:
            from .perception import get_ui_tree_summary
        except ImportError as e:
            return _import_error("perception", e)
        try:
            tree = get_ui_tree_summary(app_name=args.app, max_depth=args.depth)
            print(tree)
            return 0
        except Exception as e:
            return _runtime_error("tree", e)

    elif args.command == "screenshot":
        try:
            from .screenshot import take_screenshot
        except ImportError as e:
            return _import_error("screenshot", e)
        try:
            img_b64 = take_screenshot()
            if args.output:
                with open(args.output, "wb") as f:
                    f.write(base64.b64decode(img_b64))
                print(f"Saved to {args.output}")
            else:
                print(f"Screenshot: {len(img_b64)} bytes (base64)")
            return 0
        except Exception as e:
            return _runtime_error("screenshot", e)

    elif args.command == "elements":
        try:
            from .annotated_screenshot import take_annotated_screenshot
        except ImportError as e:
            return _import_error("annotated_screenshot", e)
        try:
            _, elements = take_annotated_screenshot(source=args.source, max_elements=args.max)
            if not elements:
                print("No interactive elements found.")
                return 0
            print(f"Found {len(elements)} interactive elements:")
            for el in elements:
                cx, cy = el.get("center", [None, None])
                print(f"[{el.get('index')}] {el.get('role')}: {el.get('name')} @ ({cx}, {cy})")
            return 0
        except Exception as e:
            return _runtime_error("elements", e)

    elif args.command == "find":
        try:
            from .screenshot import take_screenshot
            from .ocr_tool import ocr_find_text
        except ImportError as e:
            return _import_error("ocr_tool/screenshot", e)
        try:
            image = take_screenshot()
            matches = ocr_find_text(image, args.text)
            if not matches:
                print(f"No matches found for: {args.text}")
                return 0
            print(f"Found {len(matches)} match(es):")
            for i, m in enumerate(matches, start=1):
                cx, cy = m.get("center", [None, None])
                score = m.get("score", 0)
                print(f"{i}. '{m.get('text', '')}' @ ({cx}, {cy}) score={score:.2f}")
            return 0
        except Exception as e:
            return _runtime_error("find", e)

    elif args.command == "click":
        try:
            from .actions import click
        except ImportError as e:
            return _import_error("actions", e)
        try:
            if args.coords:
                x, y = _parse_coords(args.coords)
                click(x, y)
                print(f"Clicked at ({x}, {y})")
                return 0

            from .screenshot import take_screenshot
            from .ocr_tool import ocr_find_text
            matches = ocr_find_text(take_screenshot(), args.text)
            if not matches:
                print(f"No text match found for '{args.text}'")
                return 1
            best = sorted(matches, key=lambda m: m.get("score", 0), reverse=True)[0]
            x, y = best["center"]
            click(x, y)
            print(f"Clicked '{best.get('text', args.text)}' at ({x}, {y})")
            return 0
        except ImportError as e:
            return _import_error("ocr_tool/screenshot", e)
        except Exception as e:
            return _runtime_error("click", e)

    elif args.command == "record":
        try:
            from .recorder import start_recording
        except ImportError as e:
            return _import_error("recorder", e)
        try:
            rec_dir = os.path.join(os.path.dirname(__file__), "..", "recordings")
            os.makedirs(rec_dir, exist_ok=True)
            safe_name = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in args.name)
            path = os.path.join(rec_dir, f"{safe_name}.json")
            rec = start_recording(filepath=path)
            print(f"Recording started: {rec.filepath}")
            print("Use agent tools/flows to generate actions, then stop with record_stop in tool mode.")
            return 0
        except Exception as e:
            return _runtime_error("record", e)

    elif args.command == "replay":
        try:
            from .recorder import play_recording
            from .agent import execute_tool
        except ImportError as e:
            return _import_error("recorder/agent", e)
        try:
            if not os.path.exists(args.file):
                print(f"Recording file not found: {args.file}", file=sys.stderr)
                return 1
            speed = args.speed if args.speed > 0 else 1.0
            delay = 0.5 / speed
            results = play_recording(args.file, execute_tool, delay=delay, dry_run=args.dry_run)
            print(f"Replay complete: {len(results)} action(s)")
            return 0
        except Exception as e:
            return _runtime_error("replay", e)

    elif args.command == "export":
        try:
            from .recorder import export_to_script
        except ImportError as e:
            return _import_error("recorder", e)
        try:
            if not os.path.exists(args.file):
                print(f"Recording file not found: {args.file}", file=sys.stderr)
                return 1
            speed = args.speed if args.speed > 0 else 1.0
            delay = 0.5 / speed
            out = export_to_script(args.file, output=args.output, delay=delay)
            print(f"Export complete: {out}")
            return 0
        except Exception as e:
            return _runtime_error("export", e)

    elif args.command == "browser":
        try:
            from .cdp_helper import get_or_create_cdp_client
        except ImportError as e:
            return _import_error("cdp_helper", e)
        try:
            client = get_or_create_cdp_client()
            if not client:
                print("CDP browser not available. Start Chromium with --remote-debugging-port=9222", file=sys.stderr)
                return 1
            client.navigate(args.url)
            print(f"Navigated: {args.url}")
            return 0
        except Exception as e:
            return _runtime_error("browser", e)

    elif args.command == "type":
        try:
            from .actions import type_text
        except ImportError as e:
            return _import_error("actions", e)
        try:
            type_text(args.text)
            print("Typed text")
            return 0
        except Exception as e:
            return _runtime_error("type", e)

    elif args.command == "key":
        try:
            from .actions import press_key
        except ImportError as e:
            return _import_error("actions", e)
        try:
            press_key(args.combo)
            print(f"Pressed: {args.combo}")
            return 0
        except Exception as e:
            return _runtime_error("key", e)

    elif args.command == "test":
        cmd = [sys.executable, "-m", "pytest", "tests/"]
        if args.verbose:
            cmd.append("-v")
        return subprocess.call(cmd)

    elif args.command == "inspect":
        return _run_inspect(args)

    elif args.command == "wait":
        try:
            return _run_wait(args)
        except ImportError as e:
            return _import_error("wait dependencies", e)
        except Exception as e:
            return _runtime_error("wait", e)

    elif args.command == "doctor":
        return _run_doctor()

    elif args.command == "annotate":
        try:
            from .annotated_screenshot import annotated_screenshot
            import json as json_mod
            b64, labeled = annotated_screenshot(sources=args.source)
            # Save image
            raw = base64.b64decode(b64)
            with open(args.output, 'wb') as f:
                f.write(raw)
            print(f"📸 Annotated screenshot saved: {args.output} ({len(labeled)} elements labeled)")
            if args.json_output:
                print(json_mod.dumps([el.to_dict() for el in labeled], indent=2, ensure_ascii=False))
            else:
                for el in labeled[:30]:
                    print(f"  [{el.index:>3}] {el.role:<16} {el.name[:40]:<40} @ ({el.center_x}, {el.center_y})")
                if len(labeled) > 30:
                    print(f"  ... and {len(labeled) - 30} more elements")
            return 0
        except Exception as e:
            return _runtime_error("annotate", e)

    elif args.command == "selftest":
        return _run_selftest(args)

    elif args.command == "version":
        print(f"clawui {VERSION}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
