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
- **持久化支持**: 新增 `DEFAULT_USER_DATA_DIR` 配置，自动使用持久 Chromium 配置文件，保留登录态、Cookie 和设置，适用于生产自动化。

### Marionette (Firefox) 自动化
- **目标**: 作为 CDP 的互补，支持 Firefox。
- **实现**: `marionette_helper.py` (协议) + `marionette_backend.py` (抽象) + 8个 agent 工具。
- **状态**: 代码完成，待实际场景测试（需用 `firefox --marionette` 启动）。

### 录制/回放
- **模块**: `src/recorder.py`，可记录所有工具调用到 JSON 并回放。

## 工具与流程
- **认证机制**: 在 `create_github_repo_cdp.py` 中实现了健壮的非交互式认证机制。脚本按顺序尝试三种方法：优先使用 `GITHUB_TOKEN` 环境变量，若失败则调用 `gh` 命令行工具获取认证，最后才回退到依赖浏览器既有登录态的 CDP 模式。
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
  - `ClawUI/check_github_issues.py` (监控 GitHub issues)
  - `tools/start_chromium_with_profile.py` (使用已有 Profile 启动，保留登录态)
- README 已更新，包含了故障排除和最佳实践。

## 框架验证与发现 (2026-03-11)
- **Google 注册自动化实测**：
  - 成功自动化完整流程：姓名 → 生日/性别 → 用户名 → 密码 → 手机验证
  - 验证了框架处理复杂多页表单、自定义 UI 组件（combobox、radio）、动态页面的能力
  - 发现硬限制：Google 反机器人检测（升级为二维码验证），注册被拦截
  - 技术教训：
    - `cdp.evaluate()` 返回 `{'result':{'type','value'}}`，取值需使用 `.get('result',{}).get('value','')`
    - 现代网页 DOM 完全自定义，不能依赖猜测的选择器，必须检查实际结构

## 今日进展 (2026-03-11)
- **Vision Backend**: 实现多模态 AI 后端 (`vision_backend.py`)，支持 Ollama/OpenAI 模型（llava, moondream, gpt-4o），用于截图驱动的自动化决策。
- **CDP 增强**:
  - `Input.dispatchKeyEvent` 实现真实键盘输入，不再依赖输入框焦点
  - `dispatch_mouse` 支持坐标点击，可操作自定义 UI 组件
  - 新增 6 个 CDP 工具，覆盖导航、表单、标签页、截图等场景
- **GitHub 登录实验**:
  - 尝试 "Continue with Google" OAuth 流程，技术步骤完成但被 Google 安全策略拦截
  - 结论：推荐使用浏览器预登录会话或 GitHub PAT 避免 OAuth
- **其他交付**:
  - `demos/simple_login_demo.py`（herokuapp 测试）
  - `demos/github_google_login.py` + 测试文档
- **Todo**: 所有核心后端完成（AT-SPI, X11, CDP, Marionette, Vision）。待测试 Firefox Marionette 实景场景。

## 最新里程碑 (2026-03-12)
- **OCR 文本定位**: 为解决 VLM 模型在 CPU 上过慢的问题，实现了基于 OCR 的快速文本定位方案 (`find_text` 工具)。
  - **技术选型**: 优先使用 RapidOCR（~150ms），备选 Tesseract（~500ms）。
  - **实现**: 新增 `src/ocr_tool.py` 模块，提供 `ocr_find_text` 函数，并将 `find_text` 工具集成到 ClawUI Agent。
  - **配套工具**: 新增 `learn_template.py` 脚本和 `click_template` 工具，用于学习和点击 UI 元素的相对坐标，实现不依赖 AI 的稳定自动化。
  - **意义**: 大幅提升了 UI 元素定位的速度和可靠性，绕过了本地 VLM 的性能瓶颈。
- **Firefox Marionette 全面测试验证**:
  - 创建 `test_firefox_marionette.py` 测试套件，包含导航、表单填写、截图、JS 执行。
  - 改进 `test_e2e.py` 中的 Marionette 测试，使其能自动启动 Firefox，无需手动开启。
  - 本地测试全部通过：4/4 单元测试 PASS，e2e 测试 PASS。
  - 意义：至此，ClawUI 四大后端（AT-SPI、X11、CDP、Marionette）全部完成并验证，可以可靠地自动化原生 Wayland 应用、XWayland 应用、Chromium 浏览器和 Firefox 浏览器，成为真正的跨浏览器、跨桌面环境的自动化平台。
- **提交**: `392a9fc` (Firefox Marionette 测试) 及后续记忆更新 `5db4a65` 已推送至 origin/main。
- **工作区状态**: 干净，无未提交变更。

## 微信开发者工具自动化测试尝试 (2026-03-12 11:15-12:00)
- **目标**: 用 ClawUI 控制微信开发者工具并创建小游戏
- **步骤**:
  1. 安装 Wine (success) - `sudo apt install wine wine64 wine32`
  2. 初始化 Wine prefix - `wineboot --init`
  3. 尝试下载微信开发者工具 Windows 版失败:
     - GitHub releases 链接版本不存在 (1.06.0)
     - 网络/证书问题影响阿里镜像源
     - 需要正确的下载链接或手动提供 exe
- **当前状态**: Wine 环境就绪，等待手动提供 `wechatdevtools.exe` 或有效下载源
- **替代方案**: 使用 CDP 浏览器自动化已成功演示（`demo_mini_game_cdp.py`）

## 代码修复总结
- cdp_click_at: 非方法 → 改为 dispatch_mouse (2处)
- Marionette: _disconnect() → close()
- test_vision_tool.py: 重建并修复
- 新增验证脚本: `scripts/validate_python_files.py`

## 状态
- **工作区**: 干净（所有更改已提交推送）。
- **未提交变更**: 无。
- **新增目录**: `scripts/` (验证工具), `tools/`, `templates/` (规划中)

## 近期行动摘要 (2026-03-12)
1. **代码审核** - 发现并修复 cdp_click_at、marionette _disconnect、test_vision_tool.py 损坏问题
2. **CDP 小游戏演示** - demo_mini_game_cdp.py 验证浏览器自动化能力
3. **Wine 环境搭建** - 为在 Linux 运行微信开发者工具准备容器
4. **安装辅助脚本** - `setup_wechat.py` 用于检测/安装/启动微信开发者工具 (Wine)
5. **新增启动工具** - `launch_app` 和 `launch_wechat_devtools` 已添加到 agent.py, 支持启动窗口程序
6. **通用 GUI 控制增强** (A/B/C):
   - **A. 增强工具集**: `list_windows`, `activate_window`, `wait_for_window`, `describe_screen`, `find_element` (fuzzy: `name_contains`, `role_contains`)
   - **B. plan_and_execute**: 高层任务自动化, 让 LLM 自主规划并执行步骤
   - **C. 通用化**: 脚本重构为任务驱动, 不硬编码 UI 文本
7. **视觉模型硬件限制**: T430 的 NVIDIA NVS 5400M + 内核 6.17 驱动编译失败; CPU-only 推理 moondream 超时 (60-180s), 不可行
8. **新方案 - 模板坐标自动化**: 创建 `learn_template.py` 记录元素相对坐标, 实现 `click_template` 工具 (基于模板+窗口几何), 无需视觉 AI

## 待办
- **测试模板系统**: 手动运行 `learn_template.py wechat_devtools` 记录"新建项目"等按钮坐标, 然后用 `click_template` 实现完整自动化
- **配置 LLM** (可选): 如有 anyrouter API key, 可启用 `plan_and_execute` 的智能规划能力

## 技术细节
- **click_template**: 加载 `templates/<app>.json`, 匹配窗口, 计算绝对坐标并点击
- **find_text**: 基于 OCR (RapidOCR/Tesseract) 的文字查找工具, 返回坐标列表
- **ocr_tool.py**: 新增 OCR 后端实现, 优先使用 RapidOCR (快 ~150ms), 回退到 Tesseract (~500ms)
- **环境要求**: 自动化需在图形会话运行 (DISPLAY/WAYLAND_DISPLAY/DBUS_SESSION_BUS_ADDRESS)
- **依赖**: OCR 功能需要手动安装 rapidocr-onnxruntime (推荐) 或 tesseract-ocr + tesseract-ocr-chi-sim
- **提交**: ClawUI `5fa417b` -> `7d02a3d` (feat: OCR tools + click_template), 本仓库 `49c5222` (docs)
- **系统健康检查**: 新增 `tools/check_system_health.py`，用于验证所有自动化后端（AT-SPI, X11, CDP, Marionette, Vision）的可用性和运行状态。
