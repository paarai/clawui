#!/usr/bin/env python3
import sys, os, time
# Add the skill's src directory to path
skill_src = os.path.join(os.path.dirname(__file__), 'skills', 'gui-automation', 'src')
sys.path.insert(0, skill_src)
from cdp_helper import get_or_create_cdp_client

cdp = get_or_create_cdp_client()
if not cdp:
    print("❌ Failed to create client")
    exit(1)

print("✅ CDP connected")

# Navigate
cdp.navigate("https://accounts.google.com/signup")
time.sleep(6)

# Test simple query
print("Testing querySelector('input[name=\"firstName\"]')...")
raw = cdp.evaluate("document.querySelector('input[name=\"firstName\"]') !== null")
print(f"Raw result: {raw}")

# Unwrap
exists = False
if raw and isinstance(raw, dict):
    if 'result' in raw:
        val = raw['result'].get('value')
        exists = bool(val)
        print(f"Value from result.key: {val}")
    else:
        exists = bool(raw)
        print(f"No result key, using raw: {raw}")
else:
    exists = bool(raw)
    print(f"Not a dict: {raw}")

print(f"Exists: {exists}")

# Try to get element properties
if exists:
    id_raw = cdp.evaluate("document.querySelector('input[name=\"firstName\"]').id")
    print(f"Element ID: {id_raw}")
else:
    # Count inputs
    count_raw = cdp.evaluate("document.querySelectorAll('input').length")
    print(f"Number of inputs: {count_raw}")
    # List some input names
    names_raw = cdp.evaluate("Array.from(document.querySelectorAll('input')).map(i=>i.name).slice(0,10)")
    print(f"Input names: {names_raw}")
