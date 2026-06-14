from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import webbrowser

import pulsectl
from pynput.keyboard import Controller, Key

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "open_browser",
            "description": "Open a web browser, optionally searching for a query or opening a URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name of the browser (e.g. chrome, firefox)",
                        "default": "default",
                    },
                    "search_query": {
                        "type": "string",
                        "description": "Text to search for",
                    },
                    "url": {"type": "string", "description": "Direct URL to open"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "system_control",
            "description": "Control system volume (up/down/mute/set)",
            "parameters": {
                "type": "object",
                "properties": {
                    "setting": {"type": "string", "enum": ["volume"]},
                    "action": {
                        "type": "string",
                        "enum": ["up", "down", "mute", "set"],
                    },
                    "value": {
                        "type": "integer",
                        "description": "Percentage value (0-100)",
                    },
                },
                "required": ["setting", "action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "app_launcher",
            "description": "Launch a desktop application",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name of the application (e.g. code, spotify, terminal)",
                    }
                },
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "simulate_keys",
            "description": "Simulate keyboard key presses or text typing",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "string",
                        "description": "Key combo (e.g. 'ctrl+c', 'alt+enter') or text",
                    }
                },
                "required": ["keys"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_reactor",
            "description": "Delegate a complex task (coding, research, planning) to the Reactor agent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Detailed description of the task for Reactor",
                    },
                    "project_dir": {
                        "type": "string",
                        "description": "Absolute path to the project directory",
                    },
                },
                "required": ["prompt"],
            },
        },
    },
]

llm = None
MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "qwen2.5-1.5b-instruct-q4_k_m.gguf")

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


def load_agent() -> None:
    global llm
    if llm is not None:
        return

    from llama_cpp import Llama

    print("[Agent] Loading Qwen model...")
    try:
        llm = Llama(
            model_path=MODEL_PATH,
            n_gpu_layers=-1,
            n_ctx=4096,
            verbose=False,
        )
        print("[Agent] Model loaded.")
    except Exception as e:
        print(f"[Agent] Error loading model: {e}")


def handle_open_browser(args: dict) -> str:
    query = args.get("search_query")
    url = args.get("url")
    app = args.get("app_name", "default").lower()

    target_url = url

    if "youtube" in app:
        if query:
            target_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        else:
            target_url = "https://www.youtube.com"
    elif "google" in app and not target_url:
        target_url = "https://www.google.com"

    if not target_url:
        if query:
            target_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        else:
            target_url = "https://www.google.com"

    print(f"[Tool] Opening: {target_url}")
    try:
        webbrowser.open(target_url)
        return f"Opened: {query if query else target_url}"
    except Exception as e:
        return f"Failed to open browser: {e}"


def handle_system_control(args: dict) -> str:
    setting = args.get("setting")
    action = args.get("action")
    value = args.get("value", 10)

    if setting != "volume":
        return f"Setting '{setting}' not supported."

    try:
        with pulsectl.Pulse("dictator-agent") as pulse:
            sink_name = pulse.server_info().default_sink_name
            sink_info = pulse.get_sink_by_name(sink_name)
            curr_vol = sink_info.volume.value_flat

            if action == "up":
                new_vol = min(1.0, curr_vol + (value / 100))
            elif action == "down":
                new_vol = max(0.0, curr_vol - (value / 100))
            elif action == "mute":
                pulse.mute(sink_info, not sink_info.mute)
                return "Mute toggled."
            elif action == "set":
                new_vol = min(1.0, max(0.0, value / 100))
            else:
                return f"Unknown action: {action}"

            pulse.volume_set_all_chans(sink_info, new_vol)
            return f"Volume set to {int(new_vol * 100)}%"
    except Exception as e:
        return f"Error controlling volume: {e}"


def handle_app_launcher(args: dict) -> str:
    app = args.get("app_name", "").lower().strip()
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


def handle_simulate_keys(args: dict) -> str:
    keys_str = args.get("keys", "").lower().replace("'", "").replace('"', "").strip()
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

            return f"Pressed combo: {keys_str}"
        else:
            if hasattr(Key, keys_str):
                k = getattr(Key, keys_str)
                keyboard.press(k)
                keyboard.release(k)
                return f"Pressed key: {keys_str}"
            else:
                keyboard.type(keys_str)
                return f"Typed: {keys_str}"
    except Exception as e:
        return f"Failed to simulate keys: {e}"


def handle_ask_reactor(args: dict) -> str:
    from .context import infer_project_context
    from .ui import monitor

    prompt = args.get("prompt", "")
    project_dir = args.get("project_dir")

    if not prompt:
        return "No prompt provided for Reactor."

    if not project_dir:
        project_dir = infer_project_context()
        if project_dir:
            print(f"[Tool] Inferred project: {project_dir}")

    monitor.update_log(f"Reactor: {prompt}")

    reactor_cmd = shutil.which("reactor")
    if not reactor_cmd:
        return "Error: 'reactor' not found in PATH."

    cmd = [reactor_cmd, "-p", prompt]

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
                print(f"[Reactor] {clean_line}")
                monitor.update_log(clean_line)
                full_output.append(clean_line)

        process.wait()

        if process.returncode != 0:
            return f"Reactor failed with code {process.returncode}"

        return "Reactor Output:\n" + "\n".join(full_output)

    except FileNotFoundError:
        return f"Error: directory '{project_dir}' not found."
    except Exception as e:
        return f"Failed to call Reactor: {e}"


TOOL_HANDLERS = {
    "open_browser": handle_open_browser,
    "system_control": handle_system_control,
    "app_launcher": handle_app_launcher,
    "simulate_keys": handle_simulate_keys,
    "ask_reactor": handle_ask_reactor,
}


def _extract_tool_call_from_content(content: str) -> list[dict] | None:
    """Fallback parser for malformed Qwen tool-call output."""
    try:
        if "<tool_call>" in content:
            content = content.split("<tool_call>")[1].split("</tool_call>")[0]

        start_idx = content.find("{")
        if start_idx == -1:
            return None

        depth = 0
        in_quote = False
        escape = False
        end_idx = -1

        for i in range(start_idx, len(content)):
            char = content[i]
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
                        end_idx = i + 1
                        break

        if end_idx == -1:
            raw = content[start_idx:] + "}" * depth
        else:
            raw = content[start_idx:end_idx]

        tool_data = json.loads(raw)

        return [
            {
                "function": {
                    "name": tool_data["name"],
                    "arguments": json.dumps(tool_data["arguments"]),
                }
            }
        ]
    except (json.JSONDecodeError, KeyError, IndexError):
        return None


def process_command(user_text: str) -> str:
    """Process a voice command through the LLM agent."""
    load_agent()
    if not llm:
        return "Agent offline (model failed to load)"

    messages = [
        {
            "role": "system",
            "content": "You are Jarvis, a helpful assistant on Linux. Use tools to fulfill requests.",
        },
        {"role": "user", "content": user_text},
    ]

    response = llm.create_chat_completion(
        messages=messages, tools=TOOLS, tool_choice="auto"
    )

    choice = response["choices"][0]["message"]
    tool_calls = choice.get("tool_calls", [])

    # Fallback extraction for malformed output
    if not tool_calls:
        content = choice.get("content", "")
        if "<tool_call>" in content or "{" in content:
            tool_calls = _extract_tool_call_from_content(content) or []

    if not tool_calls:
        return choice.get("content", "No response.")

    t_call = tool_calls[0]
    fn_name = t_call["function"]["name"]
    raw_args = t_call["function"]["arguments"]
    fn_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args

    print(f"[Agent] Call: {fn_name}({fn_args})")

    handler = TOOL_HANDLERS.get(fn_name)
    if not handler:
        return f"Unknown tool: {fn_name}"

    result = handler(fn_args)
    print(f"[Tool] Result: {result}")
    return result
