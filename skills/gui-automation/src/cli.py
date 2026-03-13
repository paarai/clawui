#!/usr/bin/env python3
"""ClawUI CLI - AI-driven GUI automation for Linux.

Usage:
    clawui run "Open Firefox and search for cats"
    clawui apps
    clawui tree --app Firefox
    clawui screenshot -o screen.png
    clawui test
"""

import sys
import argparse


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

    # Test
    test_p = subparsers.add_parser("test", help="Run core test suite")
    test_p.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    # Version
    subparsers.add_parser("version", help="Show version")

    args = parser.parse_args()

    if args.command == "run":
        from .agent import run_agent
        result = run_agent(args.task, max_steps=args.max_steps, model=args.model)
        print(f"\nResult: {result}")

    elif args.command == "apps":
        from .perception import list_applications
        apps = list_applications()
        if isinstance(apps, list):
            for app in apps:
                print(f"  • {app}")
        else:
            print(apps)

    elif args.command == "tree":
        from .perception import get_ui_tree_summary
        tree = get_ui_tree_summary(app_name=args.app, max_depth=args.depth)
        print(tree)

    elif args.command == "screenshot":
        from .screenshot import take_screenshot
        img_b64 = take_screenshot()
        if args.output:
            import base64
            with open(args.output, "wb") as f:
                f.write(base64.b64decode(img_b64))
            print(f"Saved to {args.output}")
        else:
            print(f"Screenshot: {len(img_b64)} bytes (base64)")

    elif args.command == "test":
        import subprocess
        test_script = __file__.replace("cli.py", "../tests/test_core.py")
        import os
        test_path = os.path.join(os.path.dirname(__file__), "..", "tests", "test_core.py")
        sys.exit(subprocess.call([sys.executable, test_path]))

    elif args.command == "version":
        print("clawui 0.1.0")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
