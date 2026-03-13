#!/bin/bash
# 在图形会话中运行微信开发者工具自动化
# 用法：在桌面终端中执行此脚本

export DISPLAY=${DISPLAY:-:0}
export XAUTHORITY=${XAUTHORITY:-/run/user/$(id -u)/.mutter-Xwaylandauth.*}
export WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0}
export DBUS_SESSION_BUS_ADDRESS=${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u)/bus}

cd "$(dirname "$0")"

echo "=== WeChat DevTools Automation Launcher ==="
echo "DISPLAY=$DISPLAY"
echo "WAYLAND_DISPLAY=$WAYLAND_DISPLAY"
echo "DBUS_SESSION_BUS_ADDRESS=$DBUS_SESSION_BUS_ADDRESS"
echo ""

# 检查微信开发者工具是否已安装
if ! command -v wechat-devtools &>/dev/null; then
    echo "❌ wechat-devtools 命令未找到"
    echo "请先安装: sudo snap install wechat-devtools --dangerous"
    exit 1
fi

# 运行自动化
python3 automate_wechat.py "$@"
