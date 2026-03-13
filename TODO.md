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
- [x] **Firefox Marionette 全面测试验证**
  - 创建 `test_firefox_marionette.py` 测试套件
  - 通过自动化测试：导航、表单填写、截图、JS 执行
  - 改进 e2e 测试：自动启动 Firefox（`test_e2e.py` 已更新）
- [x] 完善 README：添加故障排除和最佳实践
- [x] Firefox Marionette 生产环境部署验证（本地测试通过）
- [x] **X11 跨工作区检测**：移除 `--onlyvisible` 限制，`list_windows()` 现在能检测所有工作区的窗口，提升对 XWayland 应用的可靠性
- [x] **wait_for_element 工具**：实现元素等待机制（超时+轮询），提升自动化可靠性，避免竞态条件
- [x] **wait_for_text 工具**：基于 OCR 的文本等待（轮询直到屏幕出现指定文本），扩展可靠性至浏览器和自定义控件

## 🔨 In Progress / Partial
- [x] 集成 CDP/Marionette 到 perception.py 路由层（让 agent 自动感知并选择后端）
- [x] 自动登录机制（已实现 GITHUB_TOKEN，待 gh auth 集成）

## 📋 Next Up
- [x] 响应 GitHub Issues（如有）(Checked 2026-03-13: could not check - missing GITHUB_TOKEN/gh auth)

---
Last updated: 2026-03-13
