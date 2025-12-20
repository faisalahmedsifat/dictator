#!/bin/bash
set -e

echo "🎤 Dictator Installer (Automated)"
echo "================================"

# --- Configuration ---
MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL_DIR="src/models"
MODEL_FILE="$MODEL_DIR/qwen2.5-1.5b-instruct-q4_k_m.gguf"

# 1. System Dependencies Check
echo "[*] Checking System Dependencies..."
MISSING_DEPS=""
if ! command -v ffmpeg &> /dev/null; then MISSING_DEPS+=" ffmpeg"; fi
if ! command -v xdotool &> /dev/null; then MISSING_DEPS+=" xdotool"; fi
# Simple check for portaudio header or lib might be hard, assume user handles it or pip fails
# On Debian/Ubuntu: portaudio19-dev is needed for PyAudio (if used) or sounddevice

if [ ! -z "$MISSING_DEPS" ]; then
    echo "⚠️  Warning: Missing tools:$MISSING_DEPS"
    echo "   Please install them (e.g., 'sudo apt install$MISSING_DEPS portaudio19-dev')"
    read -p "   Press Enter to continue anyway (or Ctrl+C to abort)..."
fi

# 2. Python Environment
echo "[*] Setting up Python Environment..."
if [ ! -d "dictate" ]; then
    python3 -m venv dictate
    echo "   Created virtual environment 'dictate'."
else
    echo "   Using existing virtual environment 'dictate'."
fi

# Upgrade pip and install requirements
./dictate/bin/pip install --upgrade pip > /dev/null
./dictate/bin/pip install -r requirements.txt

# 3. Model Downloads
echo "[*] Checking Models..."
mkdir -p "$MODEL_DIR"

if [ ! -f "$MODEL_FILE" ]; then
    echo "   Downloading Qwen 2.5 1.5B (Active Agent Model)..."
    wget -O "$MODEL_FILE" "$MODEL_URL" --show-progress
else
    echo "   Agent Model (Qwen) present."
fi

# Wake Word Model
WAKE_WORD_FILE="$MODEL_DIR/hey_jarvis_v0.1.onnx"

if [ ! -f "$WAKE_WORD_FILE" ]; then
    echo "   Extracting Wake Word Model (Hey Jarvis) from package..."
    ./dictate/bin/python -c 'import openwakeword, shutil, os, sys; target=sys.argv[1]; m = next((p for p in openwakeword.get_pretrained_model_paths() if "hey_jarvis" in p), None); shutil.copy(m, target) if m else print("Error: Model not found")' "$WAKE_WORD_FILE"
else
    echo "   Wake Word Model (Hey Jarvis) present."
fi

# 4. Service Setup (Existing Logic)
echo "[*] Configuring Background Service..."

# Cleanup old
systemctl --user stop dictator 2>/dev/null || true
systemctl --user disable dictator 2>/dev/null || true
rm "$HOME/.config/systemd/user/dictator.service" 2>/dev/null || true
systemctl --user daemon-reload

# Device selection
echo "------------------------------------------------"
./dictate/bin/python src/list_devices.py
echo "------------------------------------------------"
read -p "Enter the Device ID from the list above [default: 4]: " DEV_ID
DEV_ID=${DEV_ID:-4}

DEV_NAME=$(./dictate/bin/python -c "import sounddevice as sd; print(sd.query_devices(int($DEV_ID))['name'])")
echo "    Selected Device: '$DEV_NAME'"

echo "[*] Capturing Environment..."
SERVICE_FILE="$HOME/.config/systemd/user/dictator.service"
mkdir -p $(dirname "$SERVICE_FILE")

# Capture basic env
X_DISPLAY=${DISPLAY:-:0}
X_AUTH=${XAUTHORITY:-$HOME/.Xauthority}
PULSE_SERV=${PULSE_SERVER:-}

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Dictator - Global Voice Typing Service
After=network.target sound.target

[Service]
Type=simple
Environment=PYTHONUNBUFFERED=1
Environment=DISPLAY=$X_DISPLAY
Environment=XAUTHORITY=$X_AUTH
EOF

if [ ! -z "$PULSE_SERV" ]; then
    echo "Environment=PULSE_SERVER=$PULSE_SERV" >> "$SERVICE_FILE"
fi

cat >> "$SERVICE_FILE" <<EOF
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/dictator.sh --device "$DEV_NAME"
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
EOF

# Enable
systemctl --user daemon-reload
systemctl --user enable dictator
systemctl --user restart dictator

echo "✅ Installation Complete!"
echo "   Service is running."
echo "   Start Agent Mode: Say 'Hey Jarvis, start agent'"
