# CLAWUI RELEASE NOTES

## Version: 0.1.0-alpha (2026-03-10)

### Overview
ClawUI is a universal Linux GUI automation framework built for OpenClaw. It combines AT-SPI accessibility API with screenshot-based vision to provide precise, reliable desktop control.

### Key Features
- **Hybrid Perception**: AT-SPI for structural UI (buttons, inputs) + vision fallback
- **Wayland + X11**: Works on modern GNOME via gnome-screenshot + xdotool
- **OpenClaw Integration**: Direct agent-driven mode — no external AI API needed
- **Multi-Backend**: Claude, GPT-4o, Gemini, Ollama (autonomous mode)
- **Error Recovery**: Auto-retry on transient failures

### What's Included
- `src/screenshot.py` — Cross-platform screenshot with auto-scaling
- `src/atspi_helper.py` — UI enumeration, find elements, execute actions
- `src/actions.py` — Mouse/keyboard (ydotool + xdotool)
- `src/backends.py` — AI backends (Anthropic, OpenAI, Gemini, Ollama, AnyRouter)
- `src/agent.py` — Tool-use loop for autonomous operation
- `src/main.py` — CLI entry: `clawui run "task"` / `clawui apps` / `clawui tree`
- `src/query.py` — Quick AT-SPI inspection

### Usage (OpenClaw Agent Mode)
```python
from src.atspi_helper import find_elements, do_action, get_ui_tree_summary
from src.actions import click, type_text, press_key
from src.screenshot import take_screenshot

# See what's on screen
tree = get_ui_tree_summary(max_depth=2)

# Find and click a button
buttons = find_elements(role="push button", name="Save")
if buttons:
    do_action(buttons[0], "click")

# Type text
type_text("Hello")
press_key("Return")

# Take screenshot for visual analysis
img = take_screenshot()  # base64 PNG
```

### System Requirements
- **OS**: Ubuntu 24.04 (GNOME Wayland) or X11
- **Packages**: `xdotool`, `gnome-screenshot`, `python3-pyatspi`, `gir1.2-atspi-2.0`
- **Python**: 3.10+

### Known Limitations
- NW.js/Electron apps may have inaccurate window geometry (fallback to full-screen crop)
- Wayland screenshot requires GNOME D-Bus portal (user confirmation once)
- ydotool 0.1.8 syntax differs (xdotool preferred via XWayland)

### Roadmap
- [ ] Improved window detection for Electron/NW.js
- [ ] Parallel perception pipeline (AT-SPI + vision simultaneously)
- [ ] OpenClaw skill auto-install script
- [ ] Docker image for CI/CD testing

---

**Repo name suggestion**: `clawui`
**Description**: Universal Linux GUI automation powered by AT-SPI and AI. A skill for OpenClaw.
**Topic tags**: `gui-automation`, `linux`, `at-spi`, `openclaw`, `ai-agent`, `desktop-automation`
