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
    clawui record demo
    clawui replay recordings/demo.json
    clawui browser https://example.com
    clawui type "hello"
    clawui key "ctrl+c"
"""

import argparse
import base64
import os
import subprocess
import sys

VERSION = "0.2.0"


def _import_error(module_name: str, exc: Exception) -> int:
    print(f"Error: required module '{module_name}' is unavailable: {exc}", file=sys.stderr)
    print("Tip: check optional dependencies and your environment setup.", file=sys.stderr)
    return 2


def _runtime_error(action: str, exc: Exception) -> int:
    print(f"Error while running '{action}': {exc}", file=sys.stderr)
    return 1


def _parse_coords(coords: str) -> tuple[int, int]:
    parts = [p.strip() for p in coords.split(",")]
    if len(parts) != 2:
        raise ValueError("coords must be in format x,y")
    return int(parts[0]), int(parts[1])


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

    # Version
    subparsers.add_parser("version", help="Show version")

    args = parser.parse_args()

    if args.command == "run":
        try:
            from .agent import run_agent
        except ImportError as e:
            return _import_error("agent", e)
        try:
            result = run_agent(args.task, max_steps=args.max_steps, model=args.model)
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

    elif args.command == "version":
        print(f"clawui {VERSION}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
