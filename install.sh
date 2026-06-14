#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==================================="
echo " Dictator Installer"
echo "==================================="

# --- Configuration ---
MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL_DIR="src/models"
MODEL_FILE="$MODEL_DIR/qwen2.5-1.5b-instruct-q4_k_m.gguf"
VENV_DIR=".venv"

# --- 1. System Dependencies ---
echo ""
echo "[1/5] Checking system dependencies..."

MISSING=""
for cmd in ffmpeg xdotool; do
    if ! command -v "$cmd" &>/dev/null; then
        MISSING+=" $cmd"
    fi
done

if [ -n "$MISSING" ]; then
    echo "  Missing:$MISSING"
    echo "  Install with: sudo apt install$MISSING portaudio19-dev libportaudio2"
    read -p "  Press Enter to continue or Ctrl+C to abort..."
fi

# --- 2. Python Environment ---
echo ""
echo "[2/5] Setting up Python environment..."

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "  Created virtual environment."
else
    echo "  Using existing virtual environment."
fi

"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r requirements.txt
# openwakeword requires tflite-runtime which doesn't support Python 3.13+
# We only use ONNX models, so install without deps (onnxruntime already installed above)
"$VENV_DIR/bin/pip" install openwakeword --no-deps

# --- 3. Download Models ---
echo ""
echo "[3/5] Downloading models..."
mkdir -p "$MODEL_DIR"

if [ ! -f "$MODEL_FILE" ]; then
    echo "  Downloading Qwen 2.5 1.5B (~1.2GB)..."
    wget -q --show-progress -O "$MODEL_FILE" "$MODEL_URL"
else
    echo "  Agent model present."
fi

WAKE_WORD_FILE="$MODEL_DIR/hey_jarvis_v0.1.onnx"
if [ ! -f "$WAKE_WORD_FILE" ]; then
    echo "  Extracting wake word model..."
    "$VENV_DIR/bin/python" -c "
import openwakeword, shutil, sys
paths = openwakeword.get_pretrained_model_paths()
m = next((p for p in paths if 'hey_jarvis' in p), None)
if m:
    shutil.copy(m, sys.argv[1])
    print('  Done.')
else:
    print('  Warning: hey_jarvis model not found in openwakeword package.')
" "$WAKE_WORD_FILE"
else
    echo "  Wake word model present."
fi

# Pre-download Whisper model
echo "  Caching Whisper base.en model..."
"$VENV_DIR/bin/python" -c "from faster_whisper import WhisperModel; WhisperModel('base.en', device='cpu', compute_type='int8')" 2>/dev/null

# --- 4. Select Microphone ---
echo ""
echo "[4/5] Selecting microphone..."
echo "  Available input devices:"
echo "  ---"
"$VENV_DIR/bin/python" src/list_devices.py
echo "  ---"
read -p "  Enter device ID [default: system default]: " DEV_ID

DEVICE_ARG=""
if [ -n "$DEV_ID" ]; then
    DEV_NAME=$("$VENV_DIR/bin/python" -c "import sounddevice as sd; print(sd.query_devices(int($DEV_ID))['name'])")
    echo "  Selected: '$DEV_NAME'"
    DEVICE_ARG="--device \"$DEV_NAME\""
else
    echo "  Using system default."
fi

# --- 5. Systemd Service ---
echo ""
echo "[5/5] Setting up systemd service..."

systemctl --user stop dictator 2>/dev/null || true
systemctl --user disable dictator 2>/dev/null || true

SERVICE_FILE="$HOME/.config/systemd/user/dictator.service"
mkdir -p "$(dirname "$SERVICE_FILE")"

X_DISPLAY="${DISPLAY:-:0}"
X_AUTH="${XAUTHORITY:-$HOME/.Xauthority}"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Dictator - Voice Assistant
After=graphical-session.target sound.target

[Service]
Type=simple
Environment=PYTHONUNBUFFERED=1
Environment=DISPLAY=$X_DISPLAY
Environment=XAUTHORITY=$X_AUTH
WorkingDirectory=$SCRIPT_DIR
ExecStart=$SCRIPT_DIR/dictator.sh $DEVICE_ARG
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable dictator
systemctl --user restart dictator

echo ""
echo "==================================="
echo " Installation Complete!"
echo "==================================="
echo ""
echo " Service status:  systemctl --user status dictator"
echo " View logs:       journalctl --user -u dictator -f"
echo " Manual run:      ./dictator.sh $DEVICE_ARG"
echo ""
echo " Usage:"
echo "   Say 'Hey Jarvis' or press F9 (dictate) / F10 (agent)"
echo ""
