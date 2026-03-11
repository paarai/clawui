# TODO.md - ClawUI Task List

## ✅ Done
- [x] AT-SPI 桌面感知（GTK/Qt 原生应用）
- [x] X11 感知后端（xdotool/XWayland 应用）
- [x] 感知路由层 perception.py（自动选择后端）
- [x] CDP 后端支持 Chromium（导航、JS 执行、点击）
- [x] CDP 真实键盘输入（Input.dispatchKeyEvent）
- [x] CDP 坐标点击（cdp_click_at via dispatch_mouse）
- [x] Agent 工具集：6 CDP + 10 AT-SPI/X11 工具
- [x] 多后端模型支持（Ollama/GPT-4o/Gemini/AnyRouter）
- [x] SSH key 配置 + GitHub 推送
- [x] 端到端测试脚本（test_e2e_browser, test_simple_agent）

## 🔨 In Progress
- [ ] 端到端自动化验证（GitHub 仓库创建全流程）

## ✅ Recently Done
- [x] 多标签页切换（Target.activateTarget）— cdp_list_tabs/cdp_activate_tab/cdp_new_tab/cdp_close_tab
- [x] cdp_screenshot（浏览器内部截图）— Page.captureScreenshot
- [x] 集成 CDP 到 perception.py 路由层（三后端统一感知：AT-SPI + X11 + CDP）
- [x] 完善 README（安装、配置、示例任务）

## 📋 Next Up
- [ ] Marionette 后端支持 Firefox
- [ ] 监控 GitHub Issues 并响应
- [ ] wait_for_load 使用 Page.loadEventFired

## 🧊 Backlog
- [ ] 重构 backends.py 统一工具选择
- [ ] 添加 wait_for_load 使用 Page.loadEventFired
- [ ] cdp_form_fill 自动检测表单字段并填充
- [ ] 录制/回放功能（记录操作序列）

---
Last updated: 2026-03-11 15:20 (GMT+8)
