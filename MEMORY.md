# MEMORY.md - Long-term Memory

## 身份
- 名字：龙虾 🦞
- 用户：KK，直接简洁风格，Asia/Shanghai，飞书沟通

## 环境
- OS: Ubuntu 24.04, Wayland (GNOME) + XWayland
- xdotool 通过 XWayland 在 Wayland 下工作正常（优先用它）
- ydotool 0.1.8 语法老旧，仅作备选
- gnome-screenshot 可用
- AT-SPI 正常（python3-pyatspi）

## 项目: GUI 自动化 (`projects/gui-automation/` | `clawui`)
- **定位**: Linux GUI AI 驱动自动化工具，供 OpenClaw agent 控制桌面程序、模拟用户操作。
- **仓库**: https://github.com/longgo1001/clawui.git
- **当前模式**: OpenClaw agent 直接驱动（不需外部 API key）。保留多后端扩展口（Claude/GPT-4o/Gemini/Ollama/AnyRouter）。

### Perception Layer (Integrated Backends)
- **核心架构**: `perception.py` 实现了多后端感知路由层，统一处理来自不同源的 UI 信息，为 agent 提供全面的桌面上下文。
- **四大后端**:
  1.  **AT-SPI**: 访问原生 Wayland 和 GTK/Qt 应用的无障碍树。
  2.  **X11 (`xdotool`)**: 访问 XWayland 应用（如 v2rayN）的窗口信息和基础操作。
  3.  **CDP (Chromium DevTools Protocol)**: 深度控制 Chromium/Chrome，获取 DOM 树、执行 JS、模拟真实输入。
  4.  **Marionette**: 深度控制 Firefox，功能与 CDP 类似。
- **工作流**: agent 调用 `get_ui_tree_summary()` 时，`perception.py` 会自动查询所有可用后端，并将结果合并成一个统一的、丰富的 UI 元素树，让 agent 可以无缝操作所有类型的应用。

### CDP 浏览器自动化
- **目标**: 使 Chromium 浏览器自动化可靠、通用。
- **实现**: `cdp_helper.py` (协议) + `cdp_backend.py` (抽象) + 11个 agent 工具。
- **关键技术**: 使用 `Input.dispatchKeyEvent` 模拟真实键盘输入，用坐标点击 `dispatch_mouse` 处理自定义UI组件，通过原始HTTP请求管理标签页，保证了对现代网页（如Google登录页）的兼容性。

### Marionette (Firefox) 自动化
- **目标**: 作为 CDP 的互补，支持 Firefox。
- **实现**: `marionette_helper.py` (协议) + `marionette_backend.py` (抽象) + 8个 agent 工具。
- **状态**: 代码完成，待实际场景测试（需用 `firefox --marionette` 启动）。

### 录制/回放
- **模块**: `src/recorder.py`，可记录所有工具调用到 JSON 并回放。

## 工具与流程
- **CRON 自动改进**: 配置了每 30 分钟运行的 isolated 会话 (`9f3a29ee`)，持续推动 TODO 中的任务。
- **编辑策略**: 对于频繁变更的大型文件（如 `TODO.md`), `edit` 的精确匹配容易失败。
  - **规则**: `read` 文件获取精确 `oldText` 后再调用 `edit`。
  - **实践**: 对于结构性修改或大段落更新，直接使用 `write` 全量覆盖更可靠。此规则已固化到 `AGENTS.md`。
- **测试方法**: 演样例子的 CDP 工具组合（导航→填表→截图→多标签切换）作为功能验收标准。

## 注意事项
- AnyRouter API 只给 OpenClaw 内部用，外部脚本调不了。
- Apport 已禁用（避免弹窗干扰 GUI 自动化）。
- 技能加载必须是物理副本，符号链接会被 OpenClaw 跳过。

## 最新交付物 (2026-03-11)
- **演示脚本**:
  - `demos/browser_form_demo.py` (CDP 综合演示)
  - `demos/github_repo_creation.py` (需已登录)
  - `demos/google_signup_demo.py` (Google 注册流程)
- **工具**:
  - `tools/check_issues.py` (监控 GitHub issues)
  - `tools/start_chromium_with_profile.py` (使用已有 Profile 启动，保留登录态)
- README 已更新，包含了故障排除和最佳实践。
