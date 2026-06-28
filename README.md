# Dictator

Privacy-first voice assistant with global dictation and smart agent control. Runs entirely on your machine — no cloud, no data leaves your computer.

## Features

- **Voice Dictation** — Speak and text appears in any focused window (F9 to toggle)
- **Voice Agent** — Natural language commands: open apps, control volume, search the web (F10 to toggle)
- **Wake Word** — Say "Hey Jarvis" for hands-free activation
- **System Tray** — Lives quietly in your system tray, appears only when needed
- **Cross-Platform** — Windows and Linux support

## Installation (Windows)

### From Installer

Download `DictatorSetup-2.0.0.exe` from Releases and run it. The installer provides:
- Start Menu and Desktop shortcuts
- Optional "Run at startup"
- Uninstaller in Add/Remove Programs
- First-run wizard for model downloads

### From Source

```powershell
# Clone and install
git clone https://github.com/dictator-voice/dictator
cd dictator
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[windows]"

# Run
python -m dictator
```

## Installation (Linux)

```bash
git clone https://github.com/dictator-voice/dictator
cd dictator
python -m venv .venv
source .venv/bin/activate
pip install -e ".[linux]"

# Requires: ffmpeg, xdotool, portaudio19-dev
python -m dictator
```

## Usage

| Key | Action |
|-----|--------|
| F9 | Toggle dictation mode |
| F10 | Toggle agent mode |
| Escape | Cancel current action |
| Ctrl+Shift+Space | Toggle overlay |

All keybindings are configurable via `%APPDATA%\Dictator\config\keybindings.json`.

## Architecture

Dictator v2 is built with 12 design patterns for maintainability and fault tolerance:

- **State Pattern** — Application state machine (Idle, Routing, Dictating, Agent)
- **Strategy Pattern** — Platform abstractions (Windows/Linux implementations)
- **Abstract Factory** — Platform-specific object creation
- **Observer Pattern** — Thread-safe event bus for decoupled communication
- **Command Pattern** — Agent tools as self-contained command objects
- **Singleton** — Model lifecycle management
- **Builder** — Fluent application configuration
- **Template Method** — Transcription pipeline with overridable steps
- **Circuit Breaker** — Resilient subsystems that fail gracefully
- **Null Object** — Safe fallbacks when capabilities are unavailable
- **Dependency Injection** — Testable, loosely-coupled components
- **Facade** — Simple start/stop interface hiding internal complexity

## Building the Installer

```powershell
.\installer\build.ps1
```

Requires: Python 3.11+, PyInstaller, and optionally Inno Setup for the EXE installer.

## Project Structure

```
dictator/
  core/        — Events, state machine, models, config, resilience, lifecycle
  platform/    — Interfaces + Windows/Linux/Null implementations
  agent/       — AI agent service (via CLI tools), command registry, tool implementations
  audio/       — Resilient audio stream, sound feedback
  ui/          — Overlay, system tray, hotkeys, presence detection
  utils/       — Cross-platform paths, text utilities
  app.py       — AppBuilder + DictatorApp facade
  __main__.py  — Entry point
installer/     — PyInstaller spec, Inno Setup script, build automation
```

## License

MIT
