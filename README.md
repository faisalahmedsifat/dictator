# Dictator

Local, privacy-first voice assistant for Linux. Provides global voice typing and intelligent system control — completely offline.

## Features

- **Global Dictation** — speak and text appears in any active window with live partial updates
- **Smart Agent** — natural language commands: open apps, search the web, control volume, simulate keys
- **Wake Word** — say "Hey Jarvis" for hands-free activation
- **Visual Overlay** — transparent always-on-top status indicator
- **Privacy-first** — Whisper (STT) runs locally, Claude CLI handles agent reasoning

## Requirements

- Linux with X11 (Wayland not yet supported)
- Python 3.11+
- PulseAudio or PipeWire
- [Claude CLI](https://docs.anthropic.com/en/docs/claude-cli) (for agent commands)
- System packages: `ffmpeg`, `xdotool`, `portaudio19-dev`

## Installation

### Quick Install (Recommended)

```bash
git clone https://github.com/faisalahmedsifat/dictator.git
cd dictator
make install
```

This will:
1. Check system dependencies
2. Create a Python virtual environment
3. Download AI models (~1.2GB for Qwen + Whisper)
4. Ask you to select your microphone
5. Set up and start a systemd user service

### Manual Install

```bash
# Install system deps
sudo apt install ffmpeg xdotool portaudio19-dev libportaudio2

# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Download models
mkdir -p src/models
wget -O src/models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"

# Run
python dictate.py
```

### Docker

```bash
make docker-build        # builds image with models (~3GB)
make docker-run          # runs with audio/X11 passthrough
```

Or manually:
```bash
docker build -t dictator .
docker run --rm -it --privileged --net=host \
  -e DISPLAY=$DISPLAY \
  -e PULSE_SERVER=unix:/run/user/$(id -u)/pulse/native \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v $XAUTHORITY:/root/.Xauthority:ro \
  -v /run/user/$(id -u)/pulse:/run/user/$(id -u)/pulse:ro \
  --device /dev/snd \
  dictator --device "Your Mic Name"
```

## Usage

### Wake Word

1. Say **"Hey Jarvis"**
2. Wait for the chime (overlay turns green)
3. Speak:
   - *"Start dictation"* — enters continuous typing mode
   - *"Open Spotify"* — executes as agent command
   - *"Start agent"* — enters continuous command mode

### Hotkeys

| Key | Action |
|-----|--------|
| **F9** | Toggle dictation mode |
| **F10** | Toggle agent mode |
| **Ctrl+Space** | Toggle overlay |
| **Ctrl+Alt+Enter** | Toggle log panel |
| **Ctrl+Shift+Enter** | Hide all UI |

### Agent Commands

The agent (powered by Claude CLI) understands natural language for:
- **Browser**: "Search YouTube for cats", "Open Google"
- **Volume**: "Set volume to 50%", "Mute", "Volume up"
- **Apps**: "Open VS Code", "Launch terminal"
- **Keys**: "Press Ctrl+C", "Press Alt+Tab"
- **Claude tasks**: "Refactor this code", "Write tests for this project" (runs Claude in the inferred project directory)

### CLI Options

```bash
python dictate.py --device "USB Mic"     # specify microphone
python dictate.py --model small.en       # larger Whisper model
python dictate.py --no-partial           # disable live partial text
```

## Status Indicators

| Color | State |
|-------|-------|
| Gray | Idle — listening for wake word only |
| Green | Active — dictating or listening |
| Blue | Agent — processing commands |
| Yellow | Processing — executing a tool |

## Management

```bash
make status         # check service status
make logs           # follow live logs
make stop           # stop the service
make run            # run manually (debug)
make devices        # list audio devices
make uninstall      # remove service and venv
```

## Architecture

```
dictate.py          Main coordinator (state machine)
src/
  audio.py          Mic capture, resampling, sound effects
  wake_listener.py  "Hey Jarvis" detection (openwakeword)
  transcriber.py    Real-time STT (faster-whisper)
  inject.py         Text injection via xdotool
  agent.py          Command routing via Claude CLI + tool execution
  context.py        Active window/project inference
  ui.py             Tkinter overlay
```

## License

MIT
