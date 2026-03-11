# TODO.md - My Task List

## Priority: HIGH (Your Direct Instructions)
- [x] 自适应 GUI 自动化：用龙虾自身作为 AI 后端驱动（截图→分析→操作循环）
- [x] 支持 Ollama 本地模型接入（视觉模型如 llava/bakllava）
- [x] 支持其他模型接入（OpenAI GPT-4o、Google Gemini、任意 OpenAI-compatible API）
- [x] CDP 后端支持 Chromium 浏览器自动化

## Priority: MEDIUM (Autonomous Tasks)
- [x] 调研并解决 XWayland 与 AT-SPI 不兼容问题（影响 Firefox/Chrome 自动化）- 用户添加
  - [x] 评估现有 backends.py 架构
  - [x] 搜索 Freedesktop Portal for XWayland accessibility
  - [x] 搜索 Marionette/CDP 集成方案
  - [x] 决定实施路线（混合感知 or 切换到 X11）
  - [x] 实现 X11 感知后端（x11_helper.py）- 基础功能完成
  - [x] 创建感知路由层（perception.py）- 自动选择 AT-SPI 或 X11
  - [x] 集成 perception 到 main.py - 测试通过
  - **结论：**
    - XWayland 应用确实无法被 AT-SPI 访问（Wayland 安全模型）
    - Freedesktop Accessibility Portal 仅支持原生 Wayland 应用
    - 成熟方案：浏览器原生协议（CDP for Chromium, Marionette for Firefox）
    - 多后端扩展：atspi (Wayland) + x11 (xdotool/XWayland) + cdp/marionette
    - 临时方案：切换用户到 X11 会话（最快）
- [x] 编写端到端测试脚本（包括 X11 应用控制）
  - [x] test_e2e_browser.py - 多后端测试（AT-SPI, X11, CDP）
  - [x] run_vision_agent.py - 视觉自适应 agent 原型
  - [x] test_simple_agent.py - 文本简化版测试
- [x] 完善 README 使用示例（添加 X11 使用说明）
- [x] 配置 git 凭据以推送仓库（SSH key 已添加，推送成功）
- [x] 实现 CDP 后端支持 Chromium 浏览器
  - [x] 创建 cdp_helper.py - CDP 客户端（导航、JS 执行）
  - [x] 创建 cdp_backend.py - 后端抽象
  - [x] 动态获取 WebSocket URL 并导航
  - [ ] 集成到 perception.py （待集成）
- [ ] 实现 Marionette 后端支持 Firefox
- [ ] 重构 backends.py 支持工具选择（未来工作）

## Priority: LOW (When Idle)
- [x] 审查 MEMORY.md 并更新
- [x] 优化技能元数据
- [x] 补充 PROGRESS.md 详细进度

---

Last checked: 2026-03-11 08:15 (GMT+8)
Next check: cron trigger (every 30 minutes)