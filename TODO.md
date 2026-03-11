# TODO.md - ClawUI Task List

## ✅ Done
- [x] AT-SPI 桌面感知（GTK/Qt 原生应用）
- [x] X11 感知后端（xdotool/XWayland 应用）
- [x] 感知路由层 perception.py（自动选择后端）
- [x] CDP 后端支持 Chromium（导航、JS 执行、点击、键盘、截图、标签页）
- [x] CDP 真实键盘输入（Input.dispatchKeyEvent）
- [x] CDP 坐标点击（dispatch_mouse）
- [x] Agent 工具集：11 CDP 工具 + 10+ AT-SPI/X11 工具
- [x] 多后端模型支持（Ollama/GPT-4o/Gemini/AnyRouter）
- [x] SSH key 配置 + GitHub 推送
- [x] 端到端测试脚本（test_e2e_browser, test_simple_agent）
- [x] 完善 README（含 CDP 使用说明和示例）
- [x] 创建浏览器演示脚本（browser_form_demo.py）
- [x] 创建 GitHub 仓库创建端到端演示（github_repo_creation.py）
- [x] 添加 GitHub issues 监控脚本（tools/check_issues.py）
- [x] 配置每30分钟自主改进 cron 作业
- [x] Marionette 后端支持 Firefox（代码实现完成，待启用 TCP 端口）
- [x] 录制/回放功能（src/recorder.py，支持 JSON 记录和 dry-run）

## 🔨 In Progress / Partial
- [x] 集成 CDP/Marionette 到 perception.py 路由层（让 agent 自动感知并选择后端）
- [ ] 自动登录机制（可选的 GitHub token 注入或重用 gh auth）

## 📋 Next Up
- [x] 响应 GitHub Issues（如有）(Checked at 18:31)
- [x] 完善 README：添加故障排除和最佳实践
- [x] 测试 Firefox Marionette（已通过端到端测试验证）

---
Last updated: 2026-03-11 16:35 (GMT+8)
