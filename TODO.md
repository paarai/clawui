# TODO.md - My Task List

## Priority: HIGH (Your Direct Instructions)
- (暂无)

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
- [ ] 编写端到端测试脚本（包括 X11 应用控制）
- [ ] 完善 README 使用示例（添加 X11 使用说明）
- [ ] 配置 git 凭据以推送仓库（需用户提供信息）
- [ ] 实现 CDP 后端支持 Chromium 浏览器
- [ ] 实现 Marionette 后端支持 Firefox
- [ ] 重构 backends.py 支持工具选择（未来工作）

## Priority: LOW (When Idle)
- [x] 审查 MEMORY.md 并更新
- [x] 优化技能元数据
- [x] 补充 PROGRESS.md 详细进度

---

Last checked: 2026-03-11 08:15 (GMT+8)
Next check: cron trigger (every 30 minutes)