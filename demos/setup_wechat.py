#!/usr/bin/env python3
"""
WeChat DevTools installation and automation helper.
Works with Wine on Linux, handles Chinese/English paths.
"""

import os
import subprocess
import sys
import time
import shutil

# Paths
DEFAULT_WINE_PREFIX = os.path.expanduser("~/.wine")
WECHAT_INSTALL_DIR = os.path.join(DEFAULT_WINE_PREFIX, "drive_c", "Program Files (x86)", "微信开发者工具")
WECHAT_EXE = os.path.join(WECHAT_INSTALL_DIR, "wechatdevtools.exe")

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def is_wechat_installed():
    """Check if WeChat DevTools is installed."""
    return os.path.isfile(WECHAT_EXE)

def install_wechat_devtools(installer_path):
    """Run the Windows installer under Wine."""
    if not os.path.isfile(installer_path):
        log(f"❌ Installer not found: {installer_path}")
        return False

    log(f"Running installer: {installer_path}")
    log("Using Wine to install... (this may take a few minutes)")

    # Set environment for Chinese display
    env = os.environ.copy()
    env["LANG"] = "zh_CN.UTF-8"

    try:
        # Run installer silently if possible
        subprocess.run([
            "wine", installer_path,
            "/S", "/D=C:\\Program Files (x86)\\微信开发者工具"
        ], env=env, timeout=300)
        log("✅ Installer finished")
        return is_wechat_installed()
    except subprocess.TimeoutExpired:
        log("⚠️ Installer timed out (may need manual interaction)")
        return is_wechat_installed()
    except Exception as e:
        log(f"❌ Installer error: {e}")
        return False

def launch_wechat_devtools():
    """Launch WeChat DevTools via Wine."""
    if not is_wechat_installed():
        log("❌ WeChat DevTools not installed")
        return False

    log(f"Launching: {WECHAT_EXE}")
    try:
        subprocess.Popen(["wine", WECHAT_EXE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log("✅ Launched WeChat DevTools")
        return True
    except Exception as e:
        log(f"❌ Launch failed: {e}")
        return False

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"

    if mode == "install" and len(sys.argv) > 2:
        installer = sys.argv[2]
        if install_wechat_devtools(installer):
            log("✅ Installation verified")
        else:
            log("❌ Installation may have failed")
    elif mode == "launch":
        launch_wechat_devtools()
    else:
        print("WeChat DevTools Helper")
        print("Usage:")
        print("  python3 setup_wechat.py check          - Check if installed")
        print("  python3 setup_wechat.py install <exe> - Install from installer")
        print("  python3 setup_wechat.py launch        - Launch if installed")
        print()
        if is_wechat_installed():
            print("Status: ✅ Installed")
            print(f"Location: {WECHAT_EXE}")
        else:
            print("Status: ❌ Not installed")
            print("Please obtain wechatdevtools.exe from:")
            print("  https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html")
            print("Then run: python3 setup_wechat.py install wechatdevtools.exe")

if __name__ == "__main__":
    main()
