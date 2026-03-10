# Linux AI GUI Automation Tool - 设计文档

## 概述

基于 Anthropic Computer Use 架构改造，增加 AT-SPI 无障碍 API 集成，实现截图+结构化信息混合模式的 Linux 桌面 GUI 自动化工具。

## 架构设计

```
┌─────────────────────────────────────┐
│         AI Backend (多模型支持)        │
│   Claude / GPT-4o / Gemini Vision   │
└──────────────┬──────────────────────┘
               │ 截图 + UI 结构 + 指令
               ▼
┌─────────────────────────────────────┐
│          Agent Loop (决策循环)        │
│  截图分析 → 决策 → 执行 → 验证       │
└──────┬───────────┬──────────────────┘
       │           │
       ▼           ▼
┌──────────┐ ┌──────────────┐
│ Screenshot│ │  AT-SPI      │
│ Module    │ │  Module      │
│ (视觉)    │ │ (结构化)     │
└──────┬───┘ └──────┬───────┘
       │            │
       ▼            ▼
┌─────────────────────────────────────┐
│          Action Module (执行层)       │
│  xdotool / ydotool / AT-SPI actions │
└─────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│          Linux Desktop (X11/Wayland) │
└─────────────────────────────────────┘
```

## 核心模块

### 1. Screenshot Module (`screenshot.py`)
- 截屏：支持 gnome-screenshot / scrot / grim(Wayland)
- 缩放：大分辨率自动缩放到 1280x800 级别
- 区域截图：支持截取指定区域
- 格式：PNG → base64

### 2. AT-SPI Module (`atspi_helper.py`)
- 枚举桌面所有应用和窗口
- 获取控件树（按钮、输入框、菜单等）
- 查找控件（按名称、角色、状态）
- 获取控件坐标和尺寸
- **关键优势：不需要截图就能知道界面结构**

### 3. Action Module (`actions.py`)
- 鼠标操作：点击、双击、右键、拖拽、滚动
- 键盘操作：输入文本、快捷键
- 窗口操作：聚焦、最大化、最小化、关闭
- AT-SPI 直接操作：DoAction、SetValue（部分控件）

### 4. Agent Loop (`agent.py`)
- 混合感知：先用 AT-SPI 获取结构，再截图提供视觉上下文
- 决策循环：AI 分析 → 选择操作 → 执行 → 验证
- 错误恢复：操作失败自动重试或换策略
- 对话历史管理：保留最近 N 张截图

### 5. OpenClaw Integration (`openclaw_skill.py`)
- 作为 OpenClaw skill 运行
- 通过飞书/Telegram 等渠道接收指令
- 返回截图和操作结果

## 技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| 语言 | Python 3.11+ | AI SDK 生态、AT-SPI 绑定 |
| 截图 | gnome-screenshot / scrot | 轻量、命令行友好 |
| UI 结构 | AT-SPI (python3-pyatspi) | Linux 原生无障碍 API |
| 键鼠控制 | xdotool (X11) / ydotool (Wayland) | 成熟稳定 |
| AI 后端 | Anthropic Claude (主) + OpenAI (备) | Computer Use 原生支持 |
| 图像处理 | Pillow | 截图缩放裁切 |

## 混合模式策略

1. **AT-SPI 优先**：对于可识别的标准控件（按钮、输入框、菜单），直接通过 AT-SPI 获取位置和执行操作
2. **视觉兜底**：对于自绘 UI、游戏、Electron 应用等 AT-SPI 不可达的，退回截图+AI 识别
3. **交叉验证**：操作后同时用 AT-SPI 和截图验证结果

## 与 Anthropic Computer Use 的差异

| 方面 | Anthropic 原版 | 我们的改造 |
|------|---------------|-----------|
| 感知方式 | 纯截图 | AT-SPI + 截图混合 |
| 控件识别 | AI 视觉识别坐标 | 结构化 API 直接获取 |
| 操作精度 | 依赖坐标推测 | 精确控件位置 |
| 速度 | 每步需截图+API | 简单操作无需截图 |
| 多模型 | Claude only | Claude/GPT-4o/Gemini |
| 集成 | Streamlit demo | OpenClaw skill |

## 开发计划

### Phase 1: 基础原型 (1 周)
- [x] AT-SPI 验证
- [ ] 截图模块
- [ ] 基本操作模块
- [ ] 简单 Agent Loop

### Phase 2: 混合模式 (1 周)
- [ ] AT-SPI 控件树解析
- [ ] 混合感知策略
- [ ] 多模型后端

### Phase 3: OpenClaw 集成 (3-5 天)
- [ ] Skill 封装
- [ ] 飞书/消息渠道集成
- [ ] 截图传输

### Phase 4: 优化和完善 (持续)
- [ ] 错误恢复
- [ ] Wayland 支持
- [ ] 性能优化
- [ ] 测试覆盖

## 风险评估

| 风险 | 等级 | 缓解 |
|------|------|------|
| AT-SPI 覆盖不全 | 中 | 视觉模式兜底 |
| Wayland 兼容性 | 中 | 优先 X11，渐进支持 |
| AI API 延迟 | 中 | 本地缓存+AT-SPI 加速 |
| Electron 应用 AT-SPI 支持差 | 高 | 这类应用退回纯视觉模式 |
| 安全性（AI 操作桌面） | 高 | 操作确认机制+沙箱 |
