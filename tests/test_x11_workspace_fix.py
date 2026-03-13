#!/usr/bin/env python3
"""Test X11 window detection across all workspaces."""

import sys
import os

# Add the skill path
sys.path.insert(0, '/home/hung/.openclaw/workspace/skills/gui-automation')

def test_x11_window_detection():
    """Test that X11 window detection works without errors."""
    try:
        from src.x11_helper import list_windows, X11Window

        print("Testing X11 window detection...")
        windows = list_windows()

        print(f"Found {len(windows)} X11 windows total:")

        # Group by class
        classes = {}
        for w in windows:
            cls = w.class_name or "unknown"
            if cls not in classes:
                classes[cls] = []
            classes[cls].append(w)

        for cls, wins in sorted(classes.items()):
            print(f"  {cls}: {len(wins)} window(s)")
            for w in wins[:3]:  # show first 3
                print(f"    - {w.title[:50] if w.title else '(no title)'} (wid={w.wid})")
            if len(wins) > 3:
                print(f"    ... and {len(wins)-3} more")

        # Verify return type
        assert isinstance(windows, list), "list_windows should return a list"
        if windows:
            assert all(isinstance(w, X11Window) for w in windows), "All items should be X11Window instances"
            print("\n✓ All assertions passed")
            return True
        else:
            print("\n⚠ No X11 windows found (this is okay if none are running)")
            return True

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_perception_layer():
    """Test that perception layer correctly routes to X11."""
    try:
        from src.perception import list_applications, get_ui_tree_summary, _is_xwayland_app

        print("\nTesting perception layer...")

        # Test is_xwayland_app helper
        assert _is_xwayland_app('firefox') == True
        assert _is_xwayland_app('chromium') == True
        assert _is_xwayland_app('gnome-calculator') == False
        print("✓ XWayland app detection works")

        # Test list_applications
        apps = list_applications()
        print(f"Found {len(apps)} applications total")
        if apps:
            print("  Sample apps:", apps[:5])

        # Test UI tree summary (combined)
        tree = get_ui_tree_summary()
        print(f"UI tree length: {len(tree)} chars")
        if tree and "No UI tree available" not in tree:
            print("UI tree preview (first 200 chars):")
            print(tree[:200] + "...")
        else:
            print("⚠ UI tree is empty (this may be expected if no GUI apps running)")

        print("✓ Perception layer test completed")
        return True

    except Exception as e:
        print(f"\n✗ Perception test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = True
    success = test_x11_window_detection() and success
    success = test_perception_layer() and success

    if success:
        print("\n=== All tests passed ===")
        sys.exit(0)
    else:
        print("\n=== Some tests failed ===")
        sys.exit(1)
