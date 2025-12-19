# 🎙️ Dictator
> Global voice typing for Linux. Fast, private, and capable.

Dictator runs in the background and types what you speak into *any* application (active window) when you press **F9**. It uses OpenAI's **Whisper** model locally for high-accuracy transcription.

## ✨ Features
*   **Global Hotkey**: Toggle dictation anywhere with `F9`.
*   **Local & Private**: Runs entirely on your machine. No cloud API keys.
*   **Fast**: Optimized for real-time usage with partial results.
*   **Smart**: Cleans up repeated words and handles punctuation automatically.
*   **Visual Feedback**: Desktop notifications ("ON 🔴" / "OFF ⚪") confirm status.

## 🚀 Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/dictator.git
    cd dictator
    ```

2.  **Run the Installer**:
    ```bash
    ./install.sh
    ```
    *   The installer will create a virtual environment, download the model, and set up a background service.
    *   It will ask you to **select your microphone** from a list.
    *   It performs a quick "Audio Check" to ensure the device works before finishing.

3.  **That's it!** The service is now running.

## 📖 Usage

1.  Click into any text field (Browser, Terminal, Editor, etc.).
2.  Press **F9** to start dictating. You will see a notification: **Dictation: ON 🔴**.
3.  Speak naturally.
4.  Press **F9** again to stop. Notification: **Dictation: OFF ⚪**.

## 🔧 Troubleshooting

If it says "ON" but doesn't type anything:
1.  Check the logs:
    ```bash
    journalctl --user -u dictator -f
    ```
2.  If you see "Audio Level Peak: 0.00" or silence errors, you likely picked the wrong device.
3.  **Fix**: Run `./install.sh` again and choose a different device index (e.g., `pulse` or `default`).

## 🗑️ Uninstalling

To remove the background service:
```bash
systemctl --user stop dictator
systemctl --user disable dictator
rm ~/.config/systemd/user/dictator.service
```
Then delete the folder.
