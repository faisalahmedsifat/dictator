#!/bin/bash
set -e

echo "🎤 Dictator Installer (Manual Calibration Mode)"
echo "=============================================="

# 0. Cleanup
echo "[*] Cleaning up previous installation..."
systemctl --user stop dictator 2>/dev/null || true
systemctl --user disable dictator 2>/dev/null || true
rm "$HOME/.config/systemd/user/dictator.service" 2>/dev/null || true
systemctl --user daemon-reload

# 1. Verification
echo "[*] Verifying manual configuration..."
echo "------------------------------------------------"
# Determine Python path safely (venv or system)
PYTHON_CMD="./dictate/bin/python"
if [ ! -f "$PYTHON_CMD" ]; then
    PYTHON_CMD="python"
fi

$PYTHON_CMD list_devices.py
echo "------------------------------------------------"
read -p "Enter the Device ID from the list above [default: 4]: " DEV_ID
DEV_ID=${DEV_ID:-4}

# Resolve ID to Name for persistence
echo "[*] Resolving Device ID $DEV_ID to Name..."
DEV_NAME=$($PYTHON_CMD -c "import sounddevice as sd; print(sd.query_devices(int($DEV_ID))['name'])")
echo "    Device Name: '$DEV_NAME'"

echo "[*] Test running with Device '$DEV_NAME' for 5 seconds..."
# Run momentarily to confirm it doesn't crash
timeout 5s ./dictator.sh --device "$DEV_NAME" || true
echo "    If that looked good (no errors), we proceed."

# 2. Capture Environment
echo "[*] Capturing environment for background service..."
# We surely need DISPLAY and XAUTHORITY.
# We might also need PULSE variables if using ALSA via Pulse.
X_DISPLAY=${DISPLAY:-:0}
X_AUTH=${XAUTHORITY:-$HOME/.Xauthority}
PULSE_SERV=${PULSE_SERVER:-}

echo "    DISPLAY: $X_DISPLAY"
echo "    XAUTHORITY: $X_AUTH"
if [ ! -z "$PULSE_SERV" ]; then
    echo "    PULSE_SERVER: $PULSE_SERV"
fi

# 3. Create Service File
# We embed the device ID directly into the service command to be sure.
SERVICE_FILE="$HOME/.config/systemd/user/dictator.service"
mkdir -p $(dirname "$SERVICE_FILE")

echo "[*] Generating $SERVICE_FILE..."

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

# 4. Enable and Start
echo "[*] Reloading systemd..."
systemctl --user daemon-reload
systemctl --user enable dictator
systemctl --user restart dictator

echo "✅ Installation Complete."
echo "   Service is running with Device ID: $DEV_ID"
echo "   Check logs: journalctl --user -u dictator -f"
