## Google 登录 GitHub 测试结果 (2026-03-11)

**流程**: GitHub 登录页 → "Continue with Google" → Google 凭证输入 → OAuth 授权

**使用环境**:
- Chromium 远程调试端口 9222
- 两种 profile 测试: 默认新实例 + 用户日常 profile (`~/snap/chromium/common/chromium/`)

**结果**:
- 页面导航、DOM 操作（点击按钮、输入邮箱）均正常
- 输入邮箱后点击"下一步"成功
- 密码字段可见且可输入，但提交后 **未发生跳转**
- 最终页面仍停留在 `accounts.google.com/v3/signin/identifier?...`（登录页）
- 未出现 GitHub OAuth 授权页

**可能原因**:
1. **Google 反机器人拦截**：检测到自动化工具（CDP 控制），触发二次验证（2FA/设备确认/captcha），但该验证界面未被触发或脚本未识别
2. **凭证验证失败**：提供的账号/密码可能不匹配，或需要打开手机确认
3. **OAuth prompt=select_account**：即使已登录 Google，也可能出现账户选择页；我们未到达该页

**结论**:
- ClawUI CDP 自动化框架能完成所有基础交互（导航、点击、输入、截图）
- Google 的网站有较强的反自动化防护，使得完全自动化登录困难
- 建议后续测试其他目标网站，或预先维持已认证的浏览器会话（手动登录一次，脚本复用该 session）

**下一步建议**:
- 测试 Outlook/其他网站注册登录，验证框架通用性
- 研究解决验证码/2FA（可能需接入 OCR 或手动介入）
- 使用预认证的浏览器 profile（手动登录后保持，脚本仅做后续操作）
