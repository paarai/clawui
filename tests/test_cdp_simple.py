#!/usr/bin/env python3
import sys, os, time
sys.path.insert(0, 'skills/gui-automation/src')
from cdp_helper import launch_chromium_with_cdp, CDPClient

print("=== CDP Connection Test ===")
print(f"Envvars: DISPLAY={os.environ.get('DISPLAY')}, XAUTHORITY={os.environ.get('XAUTHORITY')}, valid={os.path.exists(os.environ.get('XAUTHORITY','')) and os.path.getsize(os.environ.get('XAUTHORITY',''))>10}")

proc = launch_chromium_with_cdp()
if not proc:
    print("❌ Launch failed")
    exit(1)

print(f"✅ Launched (PID={proc.pid})")
time.sleep(3)

client = CDPClient()
if not client.is_available():
    print("❌ CDP not available")
    proc.terminate()
    exit(1)

print("✅ CDP available")
targets = client.list_targets()
print(f"Targets: {len(targets)}")
for t in targets:
    print(f"  {t.get('type')}: {t.get('url')}")

# Navigate
print("\nNavigating to https://accounts.google.com/signup ...")
if not client.navigate("https://accounts.google.com/signup"):
    print("❌ navigate() returned False")
else:
    print("✅ navigate() sent")

time.sleep(5)

url = client.get_page_url()
title = client.get_page_title()
print(f"URL: {url}")
print(f"Title: {title}")

# Try to get a simple element
exists = client.evaluate("document.querySelector('input') !== null")
print(f"querySelector('input'): {exists}")

# Screenshot
b64 = client.take_screenshot()
if b64:
    with open("test_cdp_screenshot.png", "wb") as f:
        f.write(b64)
    print("✅ Screenshot saved")
else:
    print("❌ Screenshot failed")

proc.terminate()
print("✅ Done")
