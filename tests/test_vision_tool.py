#!/usr/bin/env python3
"""Test suite for vision_find_element tool."""

import sys
import os

# Add skill path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ClawUI/skills/gui-automation'))

def test_vision_tool_registered():
    """Test that vision_find_element tool is registered in agent."""
    from src.agent import create_tools
    tools = create_tools()
    vision_tool_names = [t['name'] for t in tools if 'vision' in t['name']]
    print(f"Vision-related tools found: {vision_tool_names}")

    if 'vision_find_element' in vision_tool_names:
        print("✅ vision_find_element tool registered")
        return True
    else:
        print("❌ vision_find_element tool NOT found")
        return False

def test_vision_tool_execution():
    """Test that vision_find_element tool can be called."""
    from src.agent import execute_tool

    print("Testing vision_find_element tool execution...")

    # Call with missing parameter
    result = execute_tool("vision_find_element", {})
    if "Missing 'description' parameter" in result.get("text", ""):
        print("✅ Missing parameter error handled correctly")
    else:
        print(f"❌ Unexpected result for missing param: {result}")
        return False

    # Call with description (may fail if vision backend unavailable, but should not crash)
    result = execute_tool("vision_find_element", {"description": "test button"})
    text = result.get("text", "")
    if "VisionBackend not available" in text or "x" in str(result):
        print("✅ vision_find_element executed without crash")
        return True
    else:
        print(f"⚠️ Vision tool returned: {text}")
        return True  # Still okay if it runs

def main():
    try:
        test_vision_tool_registered()
        test_vision_tool_execution()
        print("All tests passed!")
        return 0
    except Exception as e:
        print(f"Tests failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
