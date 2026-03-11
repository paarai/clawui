#!/usr/bin/env python3
"""Entry point for GUI automation agent."""

import sys
import argparse
from src.agent import run_agent
# Use unified perception layer
from src.perception import list_applications, get_ui_tree_summary
from src.screenshot import take_screenshot


def main():
    parser = argparse.ArgumentParser(description="AI GUI Automation for Linux")
    subparsers = parser.add_subparsers(dest="command")

    # Run a task
    run_parser = subparsers.add_parser("run", help="Run a GUI automation task")
    run_parser.add_argument("task", help="Task description in natural language")
    run_parser.add_argument("--model", default="claude-sonnet-4-20250514", help="AI model")
    run_parser.add_argument("--max-steps", type=int, default=30, help="Max steps")

    # List apps
    subparsers.add_parser("apps", help="List running applications")

    # UI tree
    tree_parser = subparsers.add_parser("tree", help="Show UI element tree")
    tree_parser.add_argument("--app", help="Filter by app name")
    tree_parser.add_argument("--depth", type=int, default=5, help="Max depth")

    # Screenshot
    screen_parser = subparsers.add_parser("screenshot", help="Take a screenshot")
    screen_parser.add_argument("-o", "--output", help="Save to file instead of base64")

    args = parser.parse_args()

    if args.command == "run":
        result = run_agent(args.task, max_steps=args.max_steps, model=args.model)
        print(f"\nResult: {result}")

    elif args.command == "apps":
        apps = list_applications()
        for app in apps:
            print(f"  • {app}")

    elif args.command == "tree":
        tree = get_ui_tree_summary(app_name=args.app, max_depth=args.depth)
        print(tree)

    elif args.command == "screenshot":
        img_b64 = take_screenshot()
        if args.output:
            import base64
            with open(args.output, "wb") as f:
                f.write(base64.b64decode(img_b64))
            print(f"Saved to {args.output}")
        else:
            print(f"Screenshot taken ({len(img_b64)} bytes base64)")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
