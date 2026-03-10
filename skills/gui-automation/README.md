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

## Architecture

```
Perception Layer:
  - AT-SPI (pyatspi) – Fast, semantic UI tree
  - Screenshot (gnome-screenshot/scrot/grim) – Visual fallback

Action Layer:
  - xdotool (X11) / ydotool (Wayland) – Mouse & keyboard
  - AT-SPI direct actions – Click, set text, toggle

Agent Loop:
  - You (OpenClaw) are the brain – call tools sequentially
  - Optional autonomous mode: any AI backend with tool-use support
```

## Tool Reference

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

## License

MIT

## Author

Built for OpenClaw. Contributions welcome.
