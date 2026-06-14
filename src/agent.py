from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import webbrowser

import pulsectl
from pynput.keyboard import Controller, Key

APP_ALIASES = {
    "code": "code",
    "vscode": "code",
    "vs code": "code",
    "chrome": "google-chrome",
    "google chrome": "google-chrome",
    "terminal": "gnome-terminal",
    "spotify": "spotify",
    "firefox": "firefox",
    "files": "nautilus",
    "file manager": "nautilus",
}

SYSTEM_PROMPT = """\
You are Jarvis, a voice-controlled assistant on Linux. The user gives you spoken commands.
Respond with a JSON object indicating the action to take. Available actions:

1. {"action": "browser", "query": "search text"} - Google search
2. {"action": "browser", "url": "https://..."} - Open URL
3. {"action": "youtube", "query": "search text"} - YouTube search
4. {"action": "volume", "op": "up|down|mute|set", "value": 10} - Volume control
5. {"action": "app", "name": "app_name"} - Launch application
6. {"action": "keys", "combo": "ctrl+c"} - Simulate key press
7. {"action": "claude", "prompt": "detailed task"} - Delegate complex task to Claude agent
8. {"action": "reply", "text": "response"} - Just respond with text (no action needed)

Respond ONLY with valid JSON object. No explanation or markdown."""


def _parse_action(response_text: str) -> dict | None:
    """Extract JSON action from Claude's response."""
    text = response_text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find JSON object in response
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_quote = False
    escape = False
    for i in range(start, len(text)):
        char = text[i]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_quote = not in_quote
        if not in_quote:
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        return None
    return None


def _call_claude_routing(user_text: str) -> dict | None:
    """Use Claude CLI to interpret a command and return an action dict."""
    claude_cmd = shutil.which("claude")
    if not claude_cmd:
        return {"action": "reply", "text": "Error: 'claude' not found in PATH."}

    full_prompt = f"{SYSTEM_PROMPT}\n\nUser command: \"{user_text}\""

    try:
        result = subprocess.run(
            [claude_cmd, "-p", "--dangerously-skip-permissions", full_prompt],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return {"action": "reply", "text": f"Claude error: {result.stderr.strip()}"}

        return _parse_action(result.stdout)
    except subprocess.TimeoutExpired:
        return {"action": "reply", "text": "Claude timed out."}
    except Exception as e:
        return {"action": "reply", "text": f"Failed to call Claude: {e}"}


def _handle_browser(action: dict) -> str:
    url = action.get("url")
    query = action.get("query")

    if not url and query:
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    elif not url:
        url = "https://www.google.com"

    try:
        webbrowser.open(url)
        return f"Opened: {query or url}"
    except Exception as e:
        return f"Failed to open browser: {e}"


def _handle_youtube(action: dict) -> str:
    query = action.get("query", "")
    if query:
        url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
    else:
        url = "https://www.youtube.com"

    try:
        webbrowser.open(url)
        return f"YouTube: {query or 'opened'}"
    except Exception as e:
        return f"Failed to open YouTube: {e}"


def _handle_volume(action: dict) -> str:
    op = action.get("op", "up")
    value = action.get("value", 10)

    try:
        with pulsectl.Pulse("dictator-agent") as pulse:
            sink_name = pulse.server_info().default_sink_name
            sink_info = pulse.get_sink_by_name(sink_name)
            curr_vol = sink_info.volume.value_flat

            if op == "up":
                new_vol = min(1.0, curr_vol + (value / 100))
            elif op == "down":
                new_vol = max(0.0, curr_vol - (value / 100))
            elif op == "mute":
                pulse.mute(sink_info, not sink_info.mute)
                return "Mute toggled."
            elif op == "set":
                new_vol = min(1.0, max(0.0, value / 100))
            else:
                return f"Unknown volume op: {op}"

            pulse.volume_set_all_chans(sink_info, new_vol)
            return f"Volume set to {int(new_vol * 100)}%"
    except Exception as e:
        return f"Error controlling volume: {e}"


def _handle_app(action: dict) -> str:
    app = action.get("name", "").lower().strip()
    if not app:
        return "No app name provided."

    cmd = APP_ALIASES.get(app, app)

    if not shutil.which(cmd):
        return f"App '{cmd}' not found in PATH."

    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Launched {cmd}"
    except Exception as e:
        return f"Failed to launch {cmd}: {e}"


def _handle_keys(action: dict) -> str:
    keys_str = action.get("combo", "").lower().replace("'", "").replace('"', "").strip()
    if not keys_str:
        return "No keys provided."

    keyboard = Controller()

    try:
        if "+" in keys_str:
            parts = [k.strip() for k in keys_str.split("+")]
            py_keys = []
            for k in parts:
                if hasattr(Key, k):
                    py_keys.append(getattr(Key, k))
                else:
                    py_keys.append(k)

            for k in py_keys:
                keyboard.press(k)
            time.sleep(0.05)
            for k in reversed(py_keys):
                keyboard.release(k)

            return f"Pressed: {keys_str}"
        else:
            if hasattr(Key, keys_str):
                k = getattr(Key, keys_str)
                keyboard.press(k)
                keyboard.release(k)
                return f"Pressed: {keys_str}"
            else:
                keyboard.type(keys_str)
                return f"Typed: {keys_str}"
    except Exception as e:
        return f"Failed to simulate keys: {e}"


def _handle_claude_task(action: dict) -> str:
    from .context import infer_project_context
    from .ui import monitor

    prompt = action.get("prompt", "")
    if not prompt:
        return "No prompt provided."

    project_dir = infer_project_context()
    if project_dir:
        print(f"[Claude] Working in: {project_dir}")

    monitor.update_log(f"Claude: {prompt}")

    claude_cmd = shutil.which("claude")
    if not claude_cmd:
        return "Error: 'claude' not found in PATH."

    cmd = [claude_cmd, "-p", "--dangerously-skip-permissions", prompt]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=project_dir,
            text=True,
            bufsize=1,
        )

        full_output = []
        for line in iter(process.stdout.readline, ""):
            clean_line = line.strip()
            if clean_line:
                print(f"[Claude] {clean_line}")
                monitor.update_log(clean_line)
                full_output.append(clean_line)

        process.wait()

        if process.returncode != 0:
            return f"Claude failed with code {process.returncode}"

        return "Claude:\n" + "\n".join(full_output[-10:])

    except FileNotFoundError:
        return f"Error: directory '{project_dir}' not found."
    except Exception as e:
        return f"Failed to run Claude: {e}"


ACTION_HANDLERS = {
    "browser": _handle_browser,
    "youtube": _handle_youtube,
    "volume": _handle_volume,
    "app": _handle_app,
    "keys": _handle_keys,
    "claude": _handle_claude_task,
}


def process_command(user_text: str) -> str:
    """Process a voice command by routing through Claude CLI."""
    print(f"[Agent] Processing: '{user_text}'")

    action = _call_claude_routing(user_text)

    if not action:
        return "Could not understand the command."

    action_type = action.get("action", "reply")

    if action_type == "reply":
        return action.get("text", "Done.")

    handler = ACTION_HANDLERS.get(action_type)
    if not handler:
        return f"Unknown action: {action_type}"

    result = handler(action)
    print(f"[Agent] Result: {result}")
    return result
