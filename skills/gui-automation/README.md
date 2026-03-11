# ClawUI - Universal Linux GUI Automation

AI-driven desktop automation for Linux. Control any application through natural language using AT-SPI accessibility and hybrid visual perception.

## Quick Start

```bash
# Clone and setup
git clone <your-repo>
cd clawui
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Run the skill via OpenClaw (recommended)
# As an OpenClaw agent, you directly call the tools in src/

# Or standalone:
python3 -m src.main run "Open Firefox and search for 'OpenClaw'"
```

## Features

- **AT-SPI Integration**: Structural UI access (buttons, menus, text fields) with exact coordinates
- **Wayland + X11 Support**: Works on modern GNOME via ydotool/xdotool + gnome-screenshot
- **Multi-Backend AI**: Use Claude, GPT-4o, Gemini, Ollama, or drive manually (OpenClaw agent)
- **Error Recovery**: Auto-retry on backend failures
- **OpenClaw Skill**: Deploy as a skill and control via Feishu/Telegram/CLI
- **Chromium Automation (CDP)**: Full browser control via Chrome DevTools Protocol

## Architecture

```
Perception Layer:
  - AT-SPI (pyatspi) – Fast, semantic UI tree
  - Screenshot (gnome-screenshot/scrot/grim) – Visual fallback

Action Layer:
  - xdotool (X11) / ydotool (Wayland) – Mouse & keyboard
  - AT-SPI direct actions – Click, set text, toggle
  - CDP (Chrome DevTools Protocol) – Browser automation

Agent Loop:
  - You (OpenClaw) are the brain – call tools sequentially
  - Optional autonomous mode: any AI backend with tool-use support
```

## Tool Reference

### Desktop Automation (AT-SPI / X11 / Wayland)

```python
import sys
sys.path.insert(0, '/path/to/clawui')
from src.atspi_helper import list_applications, find_elements, do_action, get_ui_tree_summary
from src.screenshot import take_screenshot
from src.actions import click, type_text, press_key, double_click, right_click, drag, scroll, mouse_move, focus_window

# List running apps
apps = list_applications()

# Find all buttons
buttons = find_elements(role="push button")

# Get UI tree for a specific app
tree = get_ui_tree_summary("firefox", max_depth=3)

# Click via AT-SPI (preferred)
el = buttons[0]
do_action(el, "click")

# Fallback: click coordinates
click(100, 200)

# Type text
type_text("Hello World")
press_key("Return")

# Take a screenshot (base64 PNG)
img_b64 = take_screenshot()
```

### Browser Automation (CDP)

Requires Chromium started with `--remote-debugging-port=9222` (OpenClaw skill does this automatically).

```python
from src.cdp_helper import CDPClient

c = CDPClient()

# Navigate
c.navigate("https://example.com")

# Click element by CSS selector
c.click_element("button.submit")

# OR click at viewport coordinates (for custom UI)
c.dispatch_mouse(250, 400)

# Type text into element (real keyboard events)
c.type_text('input[name="email"]', "user@example.com")

# Press special keys
c.dispatch_key("\t")  # Tab
c.dispatch_key("\n")  # Enter

# Execute JavaScript
result = c.evaluate("document.title")

# Get page info
url = c.get_page_url()
title = c.get_page_title()

# Browser screenshot (base64 PNG)
ss_b64 = c.take_screenshot()

# Tab management
tabs = c.list_targets()
new_tab = c.new_tab("https://new.page")
c.activate_tab(target_id)
c.close_tab(target_id)
```

All CDP operations are exposed to OpenClaw agent as tools: `cdp_navigate`, `cdp_click`, `cdp_click_at`, `cdp_type`, `cdp_eval`, `cdp_page_info`, `cdp_list_tabs`, `cdp_new_tab`, `cdp_activate_tab`, `cdp_close_tab`, `cdp_screenshot`.

## Demos

### Browser Form Demo
Demonstrates all 11 CDP tools on httpbin.org/forms/post:
```bash
cd projects/gui-automation
python3 demos/browser_form_demo.py
```

### GitHub Repository Creation (E2E)
Automates full repo creation, assuming Chromium default profile is logged into GitHub.
```bash
python3 demos/github_repo_creation.py
```
Ensure a browser is running with `--remote-debugging-port=9222`.

## Requirements

- Linux with AT-SPI (GNOME recommended)
- Python 3.10+
- Dependencies: `pyatspi`, `Pillow`, `anthropic` (optional)
- System tools: `xdotool`, `gnome-screenshot` (or `scrot`/`grim`)

```bash
sudo apt-get install -y python3-pyatspi gir1.2-atspi-2.0 \
    python3-pil python3-pip xdotool gnome-screenshot
pip install -r requirements.txt
```

## Configuration

Environment variables:

- `GUI_AI_MODEL`: AI model for autonomous mode (e.g., `claude-3-5-sonnet-20241022`, `gpt-4o`, `llava:7b`)
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`: respective API keys
- `OLLAMA_BASE_URL`: Ollama API URL (default: `http://localhost:11434`)
- `ANYROUTER_API_KEY`: OpenClaw's internal backend (auto-loaded from config)

## CDP (Browser) Setup

Automatically launched by OpenClaw skill with:
```
chromium --remote-debugging-port=9222 --remote-allow-origins="*"
```

To run standalone:
```bash
snap run chromium --remote-debugging-port=9222 --remote-allow-origins="*" &
```

## Project Structure

```
clawui/
├── src/
│   ├── screenshot.py    # Wayland/X11 screenshot with scaling
│   ├── atspi_helper.py  # AT-SPI UI enumeration and actions
│   ├── actions.py       # Mouse/keyboard operations
│   ├── backends.py      # AI backends (Claude, OpenAI, Gemini, Ollama, AnyRouter)
│   ├── agent.py         # Decision loop (tool-use)
│   ├── main.py          # CLI entry point
│   └── query.py         # Quick AT-SPI queries
├── DESIGN.md            # Architecture deep dive
├── PROGRESS.md          # Development status
└── SKILL.md             # OpenClaw skill manifest
```

## Troubleshooting

### AT-SPI not detecting applications

**Symptom:** `list_applications()` returns empty or missing apps.

```bash
# Check AT-SPI is running
python3 -c "import pyatspi; print(len(pyatspi.Registry.getDesktop(0)))"
# Should print > 0

# Enable AT-SPI if disabled
gsettings set org.gnome.desktop.interface toolkit-accessibility true
# Then log out/in
```

**Common causes:**
- AT-SPI disabled in GNOME settings
- Running in a minimal session (no accessibility bus)
- Snap/Flatpak apps may have limited AT-SPI exposure

### XWayland apps not visible via AT-SPI

**Symptom:** Firefox, Chromium, or Electron apps don't appear in AT-SPI tree.

This is a known Wayland limitation. ClawUI handles this with multiple backends:
- **Chromium/Chrome** → Use CDP backend (`cdp_*` tools)
- **Firefox** → Use Marionette backend (`ff_*` tools) with `firefox --marionette --marionette-port 2828`
- **Other X11 apps** → Use X11 backend (xdotool) — works if app runs under XWayland

### CDP connection fails

**Symptom:** `CDPClient()` raises connection error.

```bash
# Check if Chromium is running with debug port
curl -s http://localhost:9222/json/version | python3 -m json.tool

# If nothing, restart Chromium with:
snap run chromium --remote-debugging-port=9222 --remote-allow-origins="*" &

# If using a profile, use --user-data-dir to avoid conflicts:
snap run chromium --remote-debugging-port=9222 --remote-allow-origins="*" \
  --user-data-dir="$HOME/snap/chromium/common/chromium-debug"
```

**Snap-specific issues:**
- Chromium snap may ignore `--remote-debugging-port` if another instance is running
- Kill all Chromium processes first: `pkill -f chromium`
- Use `snap run chromium` (not just `chromium`)

### Screenshot fails

**Symptom:** `take_screenshot()` returns None or errors.

```bash
# Check available screenshot tools (tried in order):
which gnome-screenshot  # GNOME
which scrot             # X11
which grim              # Wayland (sway/wlroots)

# Install if missing:
sudo apt install gnome-screenshot  # or scrot
```

### xdotool doesn't work on Wayland

xdotool only works with X11/XWayland windows. On pure Wayland:
- Use AT-SPI `do_action()` for clicking buttons/menus
- Use `ydotool` for mouse/keyboard (requires ydotoold daemon)
- CDP/Marionette for browser automation

### Agent tools return no results

**Symptom:** `find_elements()` or `get_ui_tree_summary()` returns empty.

- Ensure the target app is **focused and visible** (not minimized)
- Try increasing `max_depth` (default 3 may miss deeply nested elements)
- Some apps expose minimal AT-SPI trees — use screenshot + coordinates as fallback

## Best Practices

### For OpenClaw Integration

1. **Use the perception layer** — Don't call backends directly. `perception.py` auto-routes to the best backend (AT-SPI → X11 → CDP → Marionette).

2. **Prefer AT-SPI actions over coordinate clicks** — `do_action(element, "click")` is more reliable than `click(x, y)` because it doesn't depend on window position.

3. **Use CDP for all browser work** — AT-SPI can't see inside web pages. CDP gives you full DOM access, form filling, and JavaScript execution.

4. **Chain tools, don't guess** — Read the UI tree first (`get_ui_tree_summary`), find the element, then act. Don't assume button positions.

### For Reliability

1. **Add small delays between actions** — UI needs time to update. A 0.5s sleep between click and read prevents stale state.

2. **Verify after acting** — After clicking a button, re-read the UI tree to confirm the expected change happened.

3. **Use CSS selectors for CDP** — `cdp_click("button.submit")` is more stable than coordinate clicks. Fall back to `cdp_click_at(x, y)` only for custom UI components.

4. **Handle popups and dialogs** — Check for unexpected modal dialogs before assuming your action failed.

### For Development

1. **Test with `test_e2e_browser.py`** — Run the E2E test suite after changes to catch regressions.

2. **Keep backends independent** — Each backend (AT-SPI, X11, CDP, Marionette) should work standalone. The perception layer composes them.

3. **Log tool calls** — When debugging agent behavior, enable verbose logging to see which tools were called and their return values.

## License

MIT

## Author

Built for OpenClaw. Contributions welcome.
