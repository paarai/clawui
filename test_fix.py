#!/usr/bin/env python3
"""Test that ensure_gui_environment sets DISPLAY/XAUTHORITY even without prior env."""
import os, sys

# Clear environment to simulate cron
os.environ.pop('DISPLAY', None)
os.environ.pop('XAUTHORITY', None)
os.environ.pop('WAYLAND_DISPLAY', None)

print("Before import:")
print("  DISPLAY:", os.environ.get('DISPLAY'))
print("  XAUTHORITY:", os.environ.get('XAUTHORITY'))
print("  WAYLAND_DISPLAY:", os.environ.get('WAYLAND_DISPLAY'))

# Import the module (this triggers ensure_gui_environment)
sys.path.insert(0, 'skills/gui-automation/src')
import cdp_helper

print("\nAfter import:")
print("  DISPLAY:", os.environ.get('DISPLAY'))
print("  XAUTHORITY:", os.environ.get('XAUTHORITY'))
print("  WAYLAND_DISPLAY:", os.environ.get('WAYLAND_DISPLAY'))

# Also check that we can get a CDP client (it will try to launch if none)
print("\nAttempting to get CDP client...")
client = cdp_helper.get_or_create_cdp_client()
if client:
    print("SUCCESS: CDP client obtained")
    print("  Available:", client.is_available())
else:
    print("NOTE: Could not get CDP client (browser may not be installed or display issues)")
