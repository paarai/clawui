# Changelog

All notable changes to ClawUI will be documented in this file.

## [0.9.0] - 2026-03-18

### Added
- **Structured exception hierarchy** (`clawui.exceptions`): `ClawUIError` base with typed subclasses for each backend (`CDPError`, `MarionetteError`, `ATSPIError`, `X11Error`, `YdotoolError`), perception (`ElementNotFoundError`, `TextNotFoundError`, `ScreenshotError`), timeouts (`WaitTimeoutError`), agent (`ModelError`), and config (`ConfigError`)
- All exceptions re-exported from `clawui` package for convenient imports
- **ydotool backend** for pure Wayland systems: `press_key`, `scroll`, `drag`, window operations with full key mapping
- `cdp_fill` tool for reliable form input (label/placeholder/aria-label targeting with framework-safe input/change events)
- Stream capture module (`stream_capture.py`): Mutter ScreenCast D-Bus API for zero-dialog ~40 FPS capture
- Game perception module (`game_perception.py`): auto ROI detection, threat/pickup detection, cross-frame tracking

### Changed
- Migrated `cdp_backend`, `perception`, `api`, `actions`, `screenshot` to use typed exceptions instead of generic `RuntimeError`
- 135 tests passing (up from 117)

### Fixed
- CDP `cdp_fill` missing execution path
- Broken unit tests from stale mock paths after refactoring
- ydotool key mapping and scroll/drag operations

## [0.8.3] - 2026-03-16

### Added
- TOML config file support with `clawui config` CLI management
- Live run progress callbacks and CLI output
- CLI `set`/`reset` commands for reliability tuning
- JSON output mode for query commands (`--json`)
- GitHub Actions CI with lint, test, and E2E jobs
- Dockerfile with Xvfb headless environment
- PyPI publish workflow (trusted publishing on tag push)

### Fixed
- PyGObject install reliability on GitHub Actions
- CI quality checks stabilization

## [0.8.2] - 2026-03-16

### Added
- Structured logging across all core modules
- `--log-level` CLI flag and `CLAWUI_LOG_LEVEL` env var
- `clawui doctor --fix` auto-repair mode for missing deps
- Wall-clock timeout for `run_agent`

### Fixed
- Double-cropping in direct X11 region captures
- Screenshot logger configuration

## [0.8.1] - 2026-03-14

### Added
- P4 CUA optimizations: 7 new capabilities (compression, OCR, sandbox blocklist)
- P3 CUA optimizations with test fixes

## [0.8.0] - 2026-03-13

### Added
- `wait_for_element` tool: element wait mechanism with timeout + polling
- `wait_for_text` tool: OCR-based text wait for browser and custom controls
- X11 cross-workspace window detection (removed `--onlyvisible` limitation)
- Firefox Marionette backend (full test validation)
- Recording/replay functionality (`src/recorder.py`)
- Annotated screenshot (Set-of-Mark) API
- CDP backend for Chromium (navigation, JS, clicks, keyboard, screenshots, tabs)
- AT-SPI + X11 hybrid perception with automatic backend routing
- Multi-model support (Ollama, GPT-4o, Gemini, AnyRouter)
- Python API (`from clawui.api import ...`)
- CLI with subcommands: `run`, `apps`, `tree`, `screenshot`, `doctor`, `config`

[0.9.0]: https://github.com/longgo1001/clawui/compare/v0.8.3...v0.9.0
[0.8.3]: https://github.com/longgo1001/clawui/compare/v0.8.2...v0.8.3
[0.8.2]: https://github.com/longgo1001/clawui/compare/v0.8.1...v0.8.2
[0.8.1]: https://github.com/longgo1001/clawui/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/longgo1001/clawui/releases/tag/v0.8.0
