# 🎙️ Dictator
> Global voice typing and intelligent control for Linux. Fast, private, and capable.

Dictator acts as your personal AI assistant. It provides a **Floating Visual Interface** to show you exactly what it's hearing and thinking. You can use it to type text anywhere or control your system (open apps, volume, web search) completely offline.

## ✨ Features
*   **Visual Interface**: A transparent, always-on-top overlay shows live transcription and status.
*   **Global Dictation (F9)**: Toggle high-speed voice typing anywhere.
*   **Smart Agent (F10 / "Hey Jarvis")**: Use the Qwen AI model to control your PC.
    *   **Open Apps**: "Open Firefox", "Launch VS Code"
    *   **Web Search**: "Search YouTube for tech news", "Open Google"
    *   **System Control**: "Set volume to 50%", "Mute"
    *   **Keyboard Control**: "Press Alt+F4", "Type 'Hello' for me"
*   **Local & Private**: Powered by **Whisper** (Speech) and **Qwen** (Reasoning). No cloud API keys.
*   **Visual Status**:
    *   ⚪ **Gray**: Idle
    *   🟢 **Green**: Dictating / Listening
    *   🔵 **Blue**: Agent Processing

## 🚀 Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/faisalahmedsifat/dictator.git
    cd dictator
    ```

2.  **Run the Installer**:
    ```bash
    ./install.sh
    ```
    *   Downloads required AI models (~1.2GB).
    *   Sets up the Python environment.
    *   Enables the background service and asks for your Microphone.

3.  **That's it!** The overlay should appear at the bottom of your screen.

## 📖 Usage

### 🗣️ Hands-Free (Wake Word)
1.  Say **"Hey Jarvis"**.
2.  Listen for the **Chime** and watch the Overlay turn **Green**.
3.  Speak naturally:
    *   *"Start dictation"* -> Switches to continuous typing mode.
    *   *"Open Spotify"* -> Launches the app.
    *   *"Play some music"* -> Agent interprets and acts.

### ⌨️ Hotkeys (Faster)
*   **F9**: Toggle **Dictation Mode**. (Green Indicator)
    *   Types everything you say into the active window.
    *   Press F9 again to stop.
*   **F10**: Toggle **Agent Mode**. (Blue Indicator)
    *   Say a command ("Search web for...").
    *   The Agent executes it and replies visually.

## 🔧 Troubleshooting

If the bar doesn't appear or commands aren't working:
1.  **Check Status**:
    ```bash
    systemctl --user status dictator
    ```
2.  **View Logs**:
    ```bash
    journalctl --user -u dictator -f
    ```
3.  **Manual Run**: Stop the service and run manually to see errors:
    ```bash
    systemctl --user stop dictator
    ./dictator.sh
    ```

## 🗑️ Uninstalling

```bash
systemctl --user stop dictator
systemctl --user disable dictator
rm ~/.config/systemd/user/dictator.service
# Then delete the project folder
```
