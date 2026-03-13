#!/usr/bin/env python3
import sys
sys.path.insert(0, 'skills/gui-automation/src')
from cdp_helper import inherit_gui_session_env, ensure_gui_environment
import os

print("Before inherit - DISPLAY:", os.environ.get('DISPLAY'), "XAUTHORITY:", os.environ.get('XAUTHORITY'))
inherit_gui_session_env()
print("After inherit - DISPLAY:", os.environ.get('DISPLAY'), "XAUTHORITY:", os.environ.get('XAUTHORITY'))

print("\nNow calling ensure_gui_environment()...")
ensure_gui_environment()
print("After ensure - DISPLAY:", os.environ.get('DISPLAY'), "XAUTHORITY:", os.environ.get('XAUTHORITY'))
