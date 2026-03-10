# Anthropic Computer Use 源码分析

## 仓库结构
`anthropic-quickstarts/computer-use-demo/`

## 核心模块

### 1. computer.py (490行) — 主工具
- **BaseComputerTool**: 基础类，处理截图和键鼠操作
- 支持 3 个版本：20241022 / 20250124 / 20251124
- 操作类型：key, type, mouse_move, click (left/right/middle/double/triple), drag, scroll, zoom, wait, hold_key

**截图机制：**
- 优先 `gnome-screenshot -f <path> -p`，备选 `scrot -p <path>`
- 截图后用 ImageMagick `convert` 缩放到目标分辨率
- 缩放目标：XGA(1024x768) / WXGA(1280x800) / FWXGA(1366x768)
- 每次操作后自动截图验证（2秒延迟）

**坐标系统：**
- API 坐标 ↔ 屏幕坐标 双向缩放
- `scale_coordinates()` 根据屏幕宽高比选择目标分辨率

**键鼠操作：**
- 全部通过 `xdotool` 实现
- 打字分块（50字符一组），每字符延迟12ms
- 拖拽：mousedown → mousemove → mouseup

### 2. loop.py — Agent 循环
- 标准的 tool-use 循环：发消息 → 收工具调用 → 执行 → 返回结果
- 支持 prompt caching（最近3轮）
- 图片截断：只保留最近 N 张截图
- System prompt 包含环境描述和操作指导

### 3. bash.py (147行) — Bash 工具
- 异步 shell 执行，超时控制

### 4. edit.py (282行) — 文本编辑工具
- str_replace 模式的文件编辑

## 优点
- 架构清晰，工具定义标准化
- 坐标缩放处理得当
- 操作覆盖全面

## 缺点
- **纯视觉**：完全依赖截图，没有 UI 结构信息
- **慢**：每步截图 + API 调用，至少 3-5 秒/步
- **脆弱**：坐标偏移就点错位置
- **仅 Claude**：深度绑定 Anthropic API
- **仅 X11**：xdotool 不支持 Wayland
