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

## 技能状态
- `gui-automation` - 已就绪，本地加载成功（无需发布到 clawhub）
- `ddg-web-search` - 已安装
