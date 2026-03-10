# AT-SPI 调研报告

## 什么是 AT-SPI
AT-SPI (Assistive Technology Service Provider Interface) 是 Linux 桌面的无障碍 API，类似于：
- Windows: UI Automation / MSAA
- macOS: Accessibility API

通过 D-Bus 暴露所有应用的 UI 控件树。

## 测试结果

### 环境
- Ubuntu (GNOME desktop)
- python3-pyatspi + gir1.2-atspi-2.0

### 能力验证

**✅ 枚举桌面应用：**
```
Desktop children: 13
  gnome-shell, gnome-terminal-server, Cloudflare Zero Trust, etc.
```

**✅ 获取控件树：** 每个应用下有完整的窗口→面板→按钮→标签层级

**✅ 控件属性：**
- name: 控件文本/标签
- role: 角色（button, text, menu, frame, etc.）
- state: 状态（focused, visible, enabled, etc.）
- position + size: 屏幕坐标和尺寸
- actions: 可执行的操作（click, activate, etc.）

### 覆盖情况

| 应用类型 | AT-SPI 支持 | 说明 |
|---------|-------------|------|
| GTK 应用 | ✅ 完整 | 原生支持 |
| Qt 应用 | ✅ 完整 | qt-at-spi bridge |
| GNOME 系列 | ✅ 完整 | 原生 |
| Electron 应用 | ⚠️ 部分 | 需开启 --force-renderer-accessibility |
| Firefox | ✅ 较好 | 有 AT-SPI 支持 |
| Chrome | ⚠️ 部分 | 需 --force-renderer-accessibility |
| 游戏/SDL | ❌ 无 | 自绘 UI，无法获取 |
| Java Swing | ✅ 较好 | Java Access Bridge |

## 关键 API

```python
import gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi

# 获取桌面
desktop = Atspi.get_desktop(0)

# 遍历应用
app = desktop.get_child_at_index(0)

# 控件信息
name = component.get_name()
role = component.get_role_name()
rect = component.get_extents(Atspi.CoordType.SCREEN)  # x, y, width, height

# 执行操作
action = component.get_action_iface()
action.do_action(0)  # 执行第一个可用操作

# 输入文本
text_iface = component.get_editable_text_iface()
text_iface.insert_text(0, "hello", -1)
```

## 与截图方案的互补性

| 场景 | AT-SPI | 截图+AI |
|------|--------|---------|
| 标准控件定位 | ✅ 精确 | ⚠️ 依赖识别 |
| 控件状态判断 | ✅ 直接读取 | ⚠️ 需视觉判断 |
| 自绘UI | ❌ 不可用 | ✅ 唯一方案 |
| 速度 | ✅ 毫秒级 | ❌ 秒级 |
| 可靠性 | ✅ 精确坐标 | ⚠️ 可能偏移 |

## 结论
AT-SPI 在 Linux 上可用性很好，能覆盖大部分标准应用。与截图结合使用，可以大幅提升操作精度和速度。
