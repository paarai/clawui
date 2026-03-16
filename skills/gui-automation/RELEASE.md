# CLAWUI RELEASE NOTES

## Version: 0.8.3 (2026-03-16)

### What's New in 0.8.x
- **TOML config file** with CLI `config set/reset` commands
- **JSON output mode** for `query` commands (`--json`)
- **Live run progress callbacks** with CLI output
- **GitHub Actions CI** with ruff linting, unit tests, and Xvfb E2E
- **Docker support** — Dockerfile with Xvfb headless environment
- **Logging migration** — structured `logging` module replaces `print()`, with `--log-level` CLI flag and `CLAWUI_LOG_LEVEL` env var
- **Wall-clock timeout** for `run_agent`
- **`clawui doctor --fix`** — auto-install missing deps
- **OCR fuzzy matching** — Levenshtein-based text matching for OCR results
- **`wait_for_element` / `wait_for_text`** — polling-based wait tools for reliability
- **Firefox Marionette backend** — full browser automation for Firefox
- **CDP backend** — Chromium automation (navigation, JS, clicks, keyboard, screenshots, tabs)
- **Recorder** — JSON record/replay with dry-run support

### Overview
ClawUI is a universal Linux GUI automation framework built for OpenClaw. It combines AT-SPI accessibility API with screenshot-based vision to provide precise, reliable desktop and browser control.

### Key Features
- **Hybrid Perception**: AT-SPI for structural UI (buttons, inputs) + vision fallback
- **Wayland + X11**: Works on modern GNOME via gnome-screenshot + xdotool
- **Browser Automation**: CDP (Chromium) + Marionette (Firefox)
- **OpenClaw Integration**: Direct agent-driven mode — no external AI API needed
- **Multi-Backend**: Claude, GPT-4o, Gemini, Ollama, AnyRouter
- **Error Recovery**: Auto-retry on transient failures
- **Configurable**: TOML config, CLI management, environment variables

### System Requirements
- **OS**: Ubuntu 22.04+ (GNOME Wayland or X11)
- **Packages**: `xdotool`, `gnome-screenshot`, `python3-pyatspi`, `gir1.2-atspi-2.0`
- **Python**: 3.10+
- **Quick check**: `clawui doctor` (auto-fix: `clawui doctor --fix`)

### Known Limitations
- NW.js/Electron apps may have inaccurate window geometry (fallback to full-screen crop)
- Wayland screenshot requires GNOME D-Bus portal (user confirmation once)

---

**Repository**: https://github.com/longgo1001/clawui
**License**: AGPL-3.0-or-later (commercial licensing available — longgo1001@gmail.com)
