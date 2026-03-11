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

## 项目
### GUI 自动化 (`projects/gui-automation/`)
- Linux GUI AI 驱动自动化工具
- 基于 Anthropic Computer Use 改造 + AT-SPI 混合感知
- 核心模块：screenshot, atspi_helper, actions, backends, agent, query, main
- 进度 98%：所有模块测试通过，差 AI Agent 端到端测试
- 当前模式：OpenClaw agent 直接驱动（不需外部 API key）
- 保留多后端扩展口（Claude/GPT-4o/Gemini/Ollama/AnyRouter）

## 注意事项
- AnyRouter API 只给 OpenClaw 内部用，外部脚本调不了
- Apport 已禁用（避免弹窗干扰 GUI 自动化）
- 微信开发者工具通过 snap 安装
- **技能加载问题（2026-03-11）：** `gui-automation` 最初放在 `projects/` 并用符号链接到 `skills/`，导致 OpenClaw 跳过（"Skipping skill path that resolves outside its configured root"）。解决：直接复制到 `skills/` 目录下（而非符号链接），现在技能状态为 ✓ ready。
- **Heartbeat 自动化（2026-03-11）：** 配置 cron 作业每30分钟自动检查 TODO.md 并执行可自主完成任务。作业 ID: `9f3a29ee-2a03-4b86-bb19-5f9a627cb515`，isolated 模式，交付:none。
- **安全审计（2026-03-11）：** 检查 `clawui` 仓库，确认无敏感信息泄露。API密钥等保存在未跟踪的 `~/.openclaw/openclaw.json` 中。添加了根 `.gitignore` 以确保本地配置文件和密钥目录被忽略，并移除了已跟踪的本地状态文件。仓库可安全发布，但推送需配置git凭据。
- **XWayland 兼容性调研与实现（2026-03-11）：** 
  - 问题：XWayland 应用（Firefox、Chromium 等）无法被 AT-SPI 访问，导致无法自动化主流浏览器
  - 原因：Wayland 安全模型阻止 XWayland 应用连接到原生 AT-SPI 服务
  - Freedesktop Accessibility Portal 仅支持原生 Wayland 应用
  - 解决方案：
    1. **短期**：切换到 X11 会话（最简单）
    2. **中期**：实现多感知后端：atspi（原生 Wayland）+ x11（xdotool/XWayland）+ cdp（Chromium DevTools Protocol）+ marionette（Firefox）
    3. **长期**：等待上游支持（Portal 扩展）
  - **已实现**：
    - `x11_helper.py`：X11 窗口列举、点击、输入等基础操作
    - `perception.py`：感知路由层，自动选择 AT-SPI 或 X11 后端
    - 集成到 `main.py`，合并输出 AT-SPI 和 X11 树
  - 现状：GNOME 原生应用（设置、文件等）继续走 AT-SPI；v2rayN 等 XWayland 应用可被 X11 后端识别；Firefox 检测需要后续优化
  - GitHub 仓库已发布：https://github.com/longgo1001/clawui.git

## CDP 浏览器自动化（2026-03-11 持续改进）
- **目标**：使 Chromium 浏览器自动化可靠、通用，供 OpenClaw agent 调用
- **核心实现**：
  - `cdp_helper.py`：CDPClient 封装 HTTP + WebSocket 命令
  - `cdp_backend.py`：后端抽象，提供 `type_in_element`, `click_at`, `press_key`, `take_screenshot` 等
  - `agent.py`：暴露 11 个 CDP 工具
- **关键技术决策**：
  - 使用 `Input.dispatchKeyEvent` 替代 `el.value` 直接赋值——对自定义表单组件（下拉、单选）更有效
  - `type_text()` 先执行 `el.click()` + `el.focus()` 再按键，避免丢失焦点
  - `activate_tab` / `close_tab` 改用原始 HTTP 请求（避免 JSON 解析错误，因为端点返回纯文本）
  - 新增 `cdp_click_at(x,y)` 用于无法通过 CSS 选择器定位的 UI（如日期选择器）
  - `take_screenshot()` 基于 `Page.captureScreenshot`，返回 base64 PNG
- **当前状态**：所有 11 个 CDP 工具已验证可用，包括多标签页列表、新建、切换、关闭
- **已知限制**：
  - 自动登录 GitHub/Google 仍需要已有会话或手动处理 2FA；Для完全自动化可预置 GitHub token 但存在安全风险
  - 坐标点击依赖于窗口尺寸和位置
- **成果**：已发布到 GitHub，创建演示脚本 `demos/browser_form_demo.py`

## Marionette (Firefox) 自动化（2026-03-16 实现）
- **目标**：无缝支持 Firefox 浏览器自动化，作为 CDP 的互补
- **核心实现**：
  - `marionette_helper.py`：基于 TCP 的 Marionette 协议客户端（WebDriver JSON 协议子集）
  - `marionette_backend.py`：后端抽象，会话管理、导航、定位、点击、键盘、截图、多标签
  - `agent.py`：暴露 8 个 Firefox 工具
- **使用**：启动 Firefox 时添加 `--marionette --marionette-port 2828`（当前版本默认启用 Marionette 但使用 Unix socket；可通过环境调整）
- **状态**：核心协议完成，待实际场景测试

## 录制/回放
- **模块**：`src/recorder.py`
- **功能**：记录所有工具调用（工具名、输入参数、结果）到 JSON 文件；可回放（dry-run 模式预览）
- **集成**：可选，需要时在 agent 中安装记录器实例

## 工具与流程
- **CRON 自动改进**：配置了每 30 分钟运行的 isolated 会话（9f3a29ee），持续推动 TODO 中的任务，无需人工干预
- **编辑策略**：对于大型配置文件（如 TODO.md），`edit` 的精确匹配容易失败；改用 `write` 重写更可靠
- **测试方法**：演样例子的 CDP 工具组合（导航→填表→截图→多标签切换）作为功能验收标准

## 最新交付物 (2026-03-11)
- `projects/gui-automation/demos/browser_form_demo.py` — 展示全部 11 个 CDP 工具的综合演示
- `projects/gui-automation/demos/github_repo_creation.py` — 端到端 GitHub 仓库创建（需已登录 Chromium）
- `projects/gui-automation/tools/check_issues.py` — 监控 GitHub issues，可集成到 cron
- `projects/gui-automation/tools/start_chromium_with_profile.py` — 使用已有 Chromium profile 启动，保留登录态
- README 更新：CDP 使用指南、演示说明、解决登录问题的启动脚本
- TODO 持续维护，Memory 定期整理
- **Edit 匹配失败处理**：对 TODO.md、README.md 等易改动文件，改用 write 全量覆盖避免精确匹配失败

## 技能状态
- `gui-automation` - 已就绪，本地加载成功（无需发布到 clawhub）
- `ddg-web-search` - 已安装
