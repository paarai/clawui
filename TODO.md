# TODO.md - ClawUI Task List

## ✅ Done
- [x] AT-SPI 桌面感知（GTK/Qt 原生应用）
- [x] X11 感知后端（xdotool/XWayland 应用）
- [x] 感知路由层 perception.py（自动选择后端）
- [x] CDP 后端支持 Chromium（导航、JS 执行、点击）
- [x] CDP 真实键盘输入（Input.dispatchKeyEvent）
- [x] CDP 坐标点击（cdp_click_at via dispatch_mouse）
- [x] Agent 工具集：11 CDP 工具 + 10+ AT-SPI/X11 工具
- [x] 多后端模型支持（Ollama/GPT-4o/Gemini/AnyRouter）
- [x] SSH key 配置 + GitHub 推送
- [x] 端到端测试脚本（test_e2e_browser, test_simple_agent）
- [x] 完善 README（含 CDP 使用说明和示例）
- [x] 创建浏览器完整演示脚本（demos/browser_form_demo.py）

## 🔨 In Progress
- [ ] 端到端自动化验证（GitHub 仓库自动创建）
- [ ] 集成 CDP 到 perception.py 路由层（让 OpenClaw 可选择 CDP 后端）
- [ ] 设置 GitHub token 用于 issues 监控

## 📋 Next Up
- [ ] Marionette 后端支持 Firefox
- [ ] issues 监控脚本 (gh 或 API)
- [ ] 录制/回放功能（记录操作序列）

---
Last updated: 2026-03-11 15:50 (GMT+8)
